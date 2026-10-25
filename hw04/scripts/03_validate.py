# 03_validate.py
# HW4 Part D: referential integrity, business-rule validation, cross-table
# reconciliations, IQR outliers and a raw-vs-clean data-quality scorecard.
# Author: Jonah Karst
# Generated: 2026-10-25
#
# Every check runs twice, on the raw tables (data/dirty) and on the clean
# tables (data/clean), with identical rules, so before/after numbers compare
# like with like. Files are read as text (dtype=str, keep_default_na=False).
#
# check_referential_integrity() is the reusable function for Assignment 5.
#
# Usage:  python hw04/scripts/03_validate.py
#
# Outputs (hw04/reports/):
#   data_quality_scorecard.csv  one row per table per stage
#   ri_results.csv              13 relationships x 2 stages
#   rule_results.csv            every business rule x 2 stages
#   reconciliations.csv         cross-table reconciliations x 2 stages
#   outliers_iqr.csv            IQR outlier flags x 2 stages

import re
from pathlib import Path

import numpy as np
import pandas as pd

HW_DIR = Path(__file__).resolve().parent.parent
STAGES = {"raw": HW_DIR / "data" / "dirty", "clean": HW_DIR / "data" / "clean"}
AUDIT_DIR = HW_DIR / "data" / "audit"
REPORTS_DIR = HW_DIR / "reports"

TABLES = ["dim_advisor", "dim_benchmark", "dim_client", "dim_date", "dim_security",
          "fact_fees", "fact_portfolio_snapshot", "fact_transactions"]


# ── Reusable referential-integrity check (keep for Assignment 5) ─────────────

def check_referential_integrity(fact_df, fact_key, dim_df, dim_key):
    """Check that every non-null fact_df[fact_key] exists in dim_df[dim_key].

    Keys are compared exactly as stored, the way a BI join compares them, so
    '45.0' does not match '45'. Works on text or typed columns. Null or blank
    keys are not orphans: they are reported separately as the null-key rate,
    and the match rate is computed over non-null keys only.

    Returns a dict:
        rows, null_key_rows, null_key_rate, matched_rows, match_rate,
        orphan_row_count, distinct_orphan_keys (sorted list),
        orphan_rows (DataFrame of the offending fact rows)
    """
    keys = fact_df[fact_key]
    is_null = keys.isna() | keys.astype(str).str.strip().eq("")
    valid_keys = dim_df[dim_key].dropna().unique()
    orphan = ~is_null & ~keys.isin(valid_keys)
    non_null = int((~is_null).sum())
    matched = non_null - int(orphan.sum())
    return {
        "rows": len(fact_df),
        "null_key_rows": int(is_null.sum()),
        "null_key_rate": is_null.mean() if len(fact_df) else 0.0,
        "matched_rows": matched,
        "match_rate": matched / non_null if non_null else 1.0,
        "orphan_row_count": int(orphan.sum()),
        "distinct_orphan_keys": sorted(keys[orphan].astype(str).unique().tolist()),
        "orphan_rows": fact_df.loc[orphan],
    }


# 10 ID-based relationships + 3 to the date table
RELATIONSHIPS = [
    ("dim_client", "advisor_id", "dim_advisor", "advisor_id"),
    ("dim_security", "benchmark_id", "dim_benchmark", "benchmark_id"),
    ("fact_fees", "client_id", "dim_client", "client_id"),
    ("fact_fees", "advisor_id", "dim_advisor", "advisor_id"),
    ("fact_portfolio_snapshot", "client_id", "dim_client", "client_id"),
    ("fact_portfolio_snapshot", "advisor_id", "dim_advisor", "advisor_id"),
    ("fact_portfolio_snapshot", "benchmark_id", "dim_benchmark", "benchmark_id"),
    ("fact_transactions", "client_id", "dim_client", "client_id"),
    ("fact_transactions", "advisor_id", "dim_advisor", "advisor_id"),
    ("fact_transactions", "security_id", "dim_security", "security_id"),
    ("fact_fees", "fee_date", "dim_date", "date"),
    ("fact_portfolio_snapshot", "snapshot_date", "dim_date", "date"),
    ("fact_transactions", "txn_date", "dim_date", "date"),
]


# ── Table metadata for the scorecard ─────────────────────────────────────────

PKS = {"dim_advisor": "advisor_id", "dim_benchmark": "benchmark_id", "dim_client": "client_id",
       "dim_date": "date_id", "dim_security": "security_id", "fact_fees": "fee_id",
       "fact_portfolio_snapshot": "snapshot_id", "fact_transactions": "txn_id"}

# Business key: the same real-world thing must appear once. For dim_client this
# is the person (not the surrogate id), which is what exposes the D-01 duplicates.
NATURAL_KEYS = {
    "dim_advisor": ["first_name", "last_name", "region"],
    "dim_benchmark": ["name"],
    "dim_client": ["first_name", "age", "zip_code", "client_since", "initial_aum"],
    "dim_date": ["date"],
    "dim_security": ["ticker"],
    "fact_fees": ["client_id", "fee_date", "fee_type"],
    "fact_portfolio_snapshot": ["client_id", "snapshot_date"],
    "fact_transactions": None,
}

# Expected type per column; columns not listed are free text
TYPES = {
    "dim_advisor": {"advisor_id": "int", "years_experience": "int", "aum_target_mm": "int"},
    "dim_benchmark": {"benchmark_id": "int"},
    "dim_client": {"client_id": "int", "age": "int", "zip_code": "zip", "initial_aum": "decimal",
                   "client_since": "date", "advisor_id": "int", "is_active": "bool"},
    "dim_date": {"date_id": "int", "date": "date", "year": "int", "quarter": "int", "month": "int",
                 "week_of_year": "int", "is_month_end": "int", "is_quarter_end": "int",
                 "is_year_end": "int", "is_trading_day": "int"},
    "dim_security": {"security_id": "int", "benchmark_id": "int", "is_etf": "bool",
                     "expense_ratio_bps": "decimal"},
    "fact_fees": {"fee_id": "int", "client_id": "int", "advisor_id": "int", "fee_date": "date",
                  "aum_basis": "decimal", "bps_charged": "decimal", "amount": "decimal",
                  "flag_aum_floor": "int"},
    "fact_portfolio_snapshot": {"snapshot_id": "int", "client_id": "int", "advisor_id": "int",
                                "benchmark_id": "int", "snapshot_date": "date", "year": "int",
                                "month": "int", "aum": "decimal", "return_ytd": "decimal",
                                "benchmark_return_ytd": "decimal", "active_alpha_ytd": "decimal",
                                "cash_pct": "decimal", "flag_aum_floor": "int",
                                "flag_return_outlier": "int"},
    "fact_transactions": {"txn_id": "int", "client_id": "int", "advisor_id": "int",
                          "security_id": "int", "txn_date": "date", "shares": "decimal",
                          "price": "decimal", "amount": "decimal",
                          "flag_after_last_snapshot": "int"},
}
# Strict formats a BI tool reads without help: no '45.0' ints, no %, no e-notation
TYPE_PATTERNS = {
    "int": r"-?\d+",
    "decimal": r"-?\d+(\.\d+)?",
    "date": r"\d{4}-\d{2}-\d{2}",
    "bool": r"True|False",
    "zip": r"\d{5}",
}

SECURITY_TXN = {"Buy", "Sell", "Dividend"}
MISSING_TOKENS = {"", "n/a", "na", "null", "nan", "missing", "-", "?"}


def expected_blank(t, name):
    """Cells where a blank is legitimate structure (decision log D-10, D-16), not missing data."""
    df = t[name]
    ok = pd.DataFrame(False, index=df.index, columns=df.columns)
    if name == "fact_transactions":
        cash = ~df["txn_type"].isin(SECURITY_TXN)
        for c in ["security_id", "shares", "price"]:
            ok[c] = cash
    if name == "dim_security":
        etf = df["is_etf"] == "True"
        ok["sector"] = etf
        ok["expense_ratio_bps"] = ~etf
    return ok


# ── Business rules (identical for raw and clean) ─────────────────────────────

def num(series):
    return pd.to_numeric(series.where(series != ""), errors="coerce")


def to_date(series):
    return pd.to_datetime(series.where(series != ""), format="%Y-%m-%d", errors="coerce")


US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "DC", "FL", "GA", "HI", "ID",
    "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO",
    "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA",
    "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
}
ACCOUNT_TYPES = {"Taxable", "IRA", "Roth IRA", "Trust", "529"}


def rng(col, lo=None, hi=None, gt=None):
    """Numeric bound (lo/hi inclusive, gt strict); rows whose value doesn't parse are not
    evaluated here (type validity covers them)."""
    def rule(df, t):
        v = num(df[col])
        ok = pd.Series(True, index=df.index)
        if lo is not None:
            ok &= v >= lo
        if hi is not None:
            ok &= v <= hi
        if gt is not None:
            ok &= v > gt
        return v.notna(), ok
    return rule


def date_rng(col, lo, hi):
    def rule(df, t):
        d = to_date(df[col])
        return d.notna(), (d >= pd.Timestamp(lo)) & (d <= pd.Timestamp(hi))
    return rule


def codes(col, allowed):
    def rule(df, t):
        return df[col] != "", df[col].isin(allowed)
    return rule


def sec_rows(df):
    return df["txn_type"].isin(SECURITY_TXN)


def rule_shares_positive(df, t):
    v = num(df["shares"])
    return sec_rows(df) & v.notna(), v > 0


def rule_security_fields(df, t):
    filled = (df["security_id"] != "") & (df["shares"] != "") & (df["price"] != "")
    empty = (df["security_id"] == "") & (df["shares"] == "") & (df["price"] == "")
    return pd.Series(True, index=df.index), filled.where(sec_rows(df), empty)


def rule_txn_amount(df, t):
    gap = (num(df["shares"]) * num(df["price"]) - num(df["amount"])).abs()
    return sec_rows(df) & gap.notna(), gap <= 0.01


def rule_fee_amount(df, t):
    calc = num(df["aum_basis"]) * num(df["bps_charged"]) / 120_000
    gap = (calc - num(df["amount"])).abs()
    return gap.notna(), gap <= 0.01


def rule_alpha(df, t):
    gap = (num(df["return_ytd"]) - num(df["benchmark_return_ytd"]) - num(df["active_alpha_ytd"])).abs()
    return gap.notna(), gap <= 1e-4


def rule_snapshot_period(df, t):
    d = to_date(df["snapshot_date"])
    ok = (d.dt.year == num(df["year"])) & (d.dt.month == num(df["month"])) & (d.dt.day == 1)
    return d.notna(), ok


def rule_first_of_month(col):
    def rule(df, t):
        d = to_date(df[col])
        return d.notna(), d.dt.day == 1
    return rule


def rule_tier_band(df, t):
    aum = num(df["initial_aum"])
    band = np.select([aum < 500_000, aum < 5_000_000], ["Retail", "HNW"], "UHNW")
    return aum.notna(), df["client_tier"] == band


def rule_etf_structure(df, t):
    etf = df["is_etf"] == "True"
    ok = np.where(etf, (df["sector"] == "") & (df["expense_ratio_bps"] != ""),
                  (df["sector"] != "") & (df["expense_ratio_bps"] == ""))
    return pd.Series(True, index=df.index), pd.Series(ok, index=df.index)


def rule_calendar(df, t):
    """Every derived attribute agrees with the date. Weekends must be non-trading days;
    weekday holidays can't be checked without an exchange calendar (none in the extract)."""
    d = to_date(df["date"])
    ok = ((d.dt.year == num(df["year"])) & (d.dt.quarter == num(df["quarter"]))
          & (d.dt.month == num(df["month"])) & (d.dt.month_name() == df["month_name"])
          & (d.dt.isocalendar().week.astype(float) == num(df["week_of_year"]))
          & (d.dt.day_name() == df["day_of_week"])
          & (d.dt.is_month_end.astype(int) == num(df["is_month_end"]))
          & (d.dt.is_quarter_end.astype(int) == num(df["is_quarter_end"]))
          & (d.dt.is_year_end.astype(int) == num(df["is_year_end"]))
          & ~((d.dt.dayofweek >= 5) & (df["is_trading_day"] == "1")))
    return d.notna(), ok


def flag_codes(col):
    def rule(df, t):
        if col not in df.columns:
            return pd.Series(False, index=df.index), pd.Series(True, index=df.index)
        return pd.Series(True, index=df.index), df[col].isin({"0", "1"})
    return rule


RULES = {
    "dim_advisor": [
        ("years_experience in [0, 60]", rng("years_experience", 0, 60)),
        ("aum_target_mm > 0", rng("aum_target_mm", gt=0)),
        ("region in code list", codes("region", {"Northeast", "Southeast", "Mid-Atlantic",
                                                 "Midwest", "West"})),
        ("certifications in code list", codes("certifications", {
            "CFA", "CFP", "CFP, CFA", "CFP, CIMA", "No Certification"})),
    ],
    "dim_benchmark": [
        ("asset_class in code list", codes("asset_class", {
            "Equity", "Fixed Income", "Multi-Asset", "International", "Small Cap",
            "Emerging", "Cash"})),
    ],
    "dim_client": [
        ("age in [18, 110]", rng("age", 18, 110)),
        ("state is USPS code", codes("state", US_STATES)),
        ("risk_profile in code list", codes("risk_profile", {
            "Conservative", "Moderately Conservative", "Balanced", "Moderately Aggressive",
            "Aggressive", "Unknown"})),
        ("client_tier in code list", codes("client_tier", {"Retail", "HNW", "UHNW"})),
        ("primary_account_type in code list", codes("primary_account_type", ACCOUNT_TYPES)),
        ("initial_aum > 0", rng("initial_aum", gt=0)),
        ("client_since <= 2024-12-31", date_rng("client_since", "1900-01-01", "2024-12-31")),
        ("client_tier matches initial_aum band", rule_tier_band),
    ],
    "dim_date": [
        ("quarter in [1, 4]", rng("quarter", 1, 4)),
        ("month in [1, 12]", rng("month", 1, 12)),
        ("week_of_year in [1, 53]", rng("week_of_year", 1, 53)),
        ("calendar attributes agree with date", rule_calendar),
    ],
    "dim_security": [
        ("asset_class in code list", codes("asset_class", {
            "Equity", "Fixed Income", "Alternative", "Cash Equivalent"})),
        ("expense_ratio_bps in [0, 300]", rng("expense_ratio_bps", 0, 300)),
        ("ETF: no sector + expense ratio; non-ETF: reverse", rule_etf_structure),
    ],
    "fact_fees": [
        ("fee_type in code list", codes("fee_type", {"Management", "Advisory", "Custodial",
                                                     "Performance"})),
        ("aum_basis > 0", rng("aum_basis", gt=0)),
        ("bps_charged in [0, 150]", rng("bps_charged", 0, 150)),
        ("amount > 0", rng("amount", gt=0)),
        ("amount = aum_basis x bps / 120,000", rule_fee_amount),
        ("fee_date in 2020-2024", date_rng("fee_date", "2020-01-01", "2024-12-31")),
        ("fee_date on 1st of month", rule_first_of_month("fee_date")),
        ("flag_aum_floor is 0/1", flag_codes("flag_aum_floor")),
    ],
    "fact_portfolio_snapshot": [
        ("aum >= 0", rng("aum", 0)),
        ("cash_pct in [0, 1]", rng("cash_pct", 0, 1)),
        ("return_ytd >= -100%", rng("return_ytd", -1)),
        ("benchmark_return_ytd >= -100%", rng("benchmark_return_ytd", -1)),
        ("account_type in code list", codes("account_type", ACCOUNT_TYPES)),
        ("alpha = return - benchmark", rule_alpha),
        ("year/month = snapshot_date, 1st of month", rule_snapshot_period),
        ("snapshot_date in 2020-2024", date_rng("snapshot_date", "2020-01-01", "2024-12-31")),
        ("flag_aum_floor is 0/1", flag_codes("flag_aum_floor")),
        ("flag_return_outlier is 0/1", flag_codes("flag_return_outlier")),
    ],
    "fact_transactions": [
        ("txn_type in code list", codes("txn_type", SECURITY_TXN | {"Deposit", "Withdrawal",
                                                                    "Advisory Fee"})),
        ("amount > 0", rng("amount", gt=0)),
        ("price > 0", rng("price", gt=0)),
        ("shares > 0 on security txns (sign rule)", rule_shares_positive),
        ("security fields filled iff Buy/Sell/Dividend", rule_security_fields),
        ("amount = shares x price", rule_txn_amount),
        ("txn_date in 2020-2024", date_rng("txn_date", "2020-01-01", "2024-12-31")),
        ("flag_after_last_snapshot is 0/1", flag_codes("flag_after_last_snapshot")),
    ],
}


# ── Checks ───────────────────────────────────────────────────────────────────

def run_ri(stage, t):
    rows = []
    for child, fk, parent, pk in RELATIONSHIPS:
        r = check_referential_integrity(t[child], fk, t[parent], pk)
        rows.append({
            "stage": stage, "relationship": f"{child}.{fk} -> {parent}.{pk}",
            "child_table": child, "rows": r["rows"],
            "match_rate_pct": round(100 * r["match_rate"], 3),
            "orphan_rows": r["orphan_row_count"],
            "distinct_orphan_keys": len(r["distinct_orphan_keys"]),
            "orphan_key_examples": " ".join(r["distinct_orphan_keys"][:5]),
            "null_key_rate_pct": round(100 * r["null_key_rate"], 3),
            "matched_non_null": r["matched_rows"],
        })
    return pd.DataFrame(rows)


def run_rules(stage, t):
    rows = []
    for name, rules in RULES.items():
        df = t[name]
        for rule_name, rule in rules:
            evaluated, passed = rule(df, t)
            n_eval = int(evaluated.sum())
            n_fail = int((evaluated & ~passed.fillna(False).astype(bool)).sum())
            rows.append({"stage": stage, "table": name, "rule": rule_name,
                         "evaluated": n_eval, "failed": n_fail,
                         "pass_pct": round(100 * (n_eval - n_fail) / n_eval, 3) if n_eval else ""})
    return pd.DataFrame(rows)


def recon(stage, name, tables, evaluated, passed, detail):
    return {"stage": stage, "reconciliation": name, "tables": tables, "evaluated": int(evaluated),
            "passed": int(passed),
            "pass_pct": round(100 * passed / evaluated, 3) if evaluated else "",
            "result": "PASS" if evaluated and passed == evaluated else "FAIL", "detail": detail}


def quarter(dates):
    """'2023Q1' labels; unparseable dates become NaN so groupby drops them (no fake quarter)."""
    d = to_date(dates)
    label = d.dt.year.astype("Int64").astype(str) + "Q" + d.dt.quarter.astype("Int64").astype(str)
    return label.where(d.notna())


def one_value_per_key(dim, key, col):
    """dim[col] per key; a key whose duplicate rows disagree maps to NaN, so it fails the check
    instead of the result depending on which copy comes first."""
    g = dim.groupby(key)[col]
    return g.first().where(g.nunique() == 1)


def run_reconciliations(stage, t, raw):
    out = []
    fee, snap, tx, cl = (t[n] for n in
                         ["fact_fees", "fact_portfolio_snapshot", "fact_transactions", "dim_client"])

    # R1: fee basis = same client-month snapshot AUM (recomputed vs stored, across tables)
    m = fee.merge(snap[["client_id", "snapshot_date", "aum"]].drop_duplicates(["client_id", "snapshot_date"]),
                  left_on=["client_id", "fee_date"], right_on=["client_id", "snapshot_date"], how="left")
    ok = (num(m["aum_basis"]) - num(m["aum"])).abs() <= 0.01
    out.append(recon(stage, "R1 fee aum_basis = snapshot aum (same client-month)",
                     "fact_fees, fact_portfolio_snapshot", len(m), ok.sum(),
                     f"{m['aum'].isna().sum()} fees with no snapshot"))

    # R2: fact advisor = the client's advisor in dim_client
    for fact in ["fact_fees", "fact_portfolio_snapshot", "fact_transactions"]:
        f = t[fact]
        dim_adv = f["client_id"].map(one_value_per_key(cl, "client_id", "advisor_id"))
        has_client = f["client_id"].isin(set(cl["client_id"]))
        out.append(recon(stage, f"R2 {fact}.advisor_id = dim_client.advisor_id",
                         f"{fact}, dim_client", has_client.sum(),
                         (has_client & (f["advisor_id"] == dim_adv)).sum(),
                         f"{(~has_client).sum()} rows with no matching client not evaluated"))

    # R3: snapshot account type = client's primary account type
    dim_type = snap["client_id"].map(one_value_per_key(cl, "client_id", "primary_account_type"))
    has_client = snap["client_id"].isin(set(cl["client_id"]))
    out.append(recon(stage, "R3 snapshot account_type = dim_client.primary_account_type",
                     "fact_portfolio_snapshot, dim_client", has_client.sum(),
                     (has_client & (snap["account_type"] == dim_type)).sum(), ""))

    # R4: Advisory Fee debits vs fee accruals per client-quarter (tests decision log D-20).
    # Which accruals the debits cover is undocumented, so test both readings.
    af = tx[tx["txn_type"] == "Advisory Fee"]
    a = num(af["amount"]).groupby([af["client_id"], quarter(af["txn_date"])]).sum()
    for label, fees in [("all fee types", fee), ("fee_type = Advisory", fee[fee["fee_type"] == "Advisory"])]:
        b = num(fees["amount"]).groupby([fees["client_id"], quarter(fees["fee_date"])]).sum()
        j = pd.concat([a.rename("debited"), b.rename("accrued")], axis=1)
        both = j.dropna()
        within = ((both["debited"] / both["accrued"] - 1).abs() <= 0.01).sum()
        out.append(recon(stage, f"R4 Advisory Fee debits = accruals ({label}) per client-quarter, within 1%",
                         "fact_transactions, fact_fees", len(j), within,
                         f"{len(j) - len(both)} client-quarters present in only one table; "
                         f"median debited/accrued = {(both['debited'] / both['accrued']).median():.3f}; "
                         f"totals ${a.sum():,.0f} debited vs ${b.sum():,.0f} accrued"))

    # R5: nothing lost in cleaning: clean + quarantined = raw, in rows AND in money.
    # Any unparseable amount fails the check rather than summing as 0.
    if stage == "clean":
        for fact, col in [("fact_transactions", "amount"), ("fact_fees", "amount"),
                          ("fact_portfolio_snapshot", "aum")]:
            parts = [pd.read_csv(p, dtype=str, keep_default_na=False)
                     for p in AUDIT_DIR.glob(f"quarantine_{fact}*.csv")]
            q_rows, q_total = sum(len(p) for p in parts), sum(num(p[col]).sum() for p in parts)
            unparseable = sum(num(df[col]).isna().sum() for df in [t[fact], raw[fact], *parts])
            clean_total, raw_total = num(t[fact][col]).sum(), num(raw[fact][col]).sum()
            ok = (abs(clean_total + q_total - raw_total) <= 0.01
                  and len(t[fact]) + q_rows == len(raw[fact]) and unparseable == 0)
            out.append(recon(stage, f"R5 {fact}.{col}: clean + quarantined = raw (rows and $)",
                             f"{fact} (raw, clean, quarantine)", 1, int(ok),
                             f"rows {len(t[fact]):,} + {q_rows:,} vs {len(raw[fact]):,}; "
                             f"clean ${clean_total:,.2f} + quarantined ${q_total:,.2f} vs raw "
                             f"${raw_total:,.2f}; unparseable values {unparseable}"))
    return pd.DataFrame(out)


def iqr_flags(series, k=1.5):
    """Tukey fences: values below Q1 - k*IQR or above Q3 + k*IQR."""
    v = num(series)
    q1, q3 = v.quantile(0.25), v.quantile(0.75)
    lo, hi = q1 - k * (q3 - q1), q3 + k * (q3 - q1)
    return (v < lo) | (v > hi), q1, q3, lo, hi


# Numeric columns with no natural upper bound; `group` re-runs the fences within each segment
IQR_COLUMNS = [
    ("fact_transactions", "amount", None),
    ("fact_transactions", "amount", "txn_type"),
    ("fact_fees", "amount", None),
    ("dim_client", "initial_aum", None),
    ("dim_client", "initial_aum", "client_tier"),
    ("fact_portfolio_snapshot", "aum", None),
]


def run_outliers(stage, t):
    rows = []
    for name, col, group in IQR_COLUMNS:
        df = t[name]
        groups = [("(all)", df)] if group is None else list(df.groupby(group))
        for g, part in groups:
            flag, q1, q3, lo, hi = iqr_flags(part[col])
            n = int(num(part[col]).notna().sum())  # same denominator for n and flagged_pct
            rows.append({"stage": stage, "table": name, "column": col,
                         "segment": "(all)" if group is None else f"{group}={g}",
                         "n": n, "q1": round(q1, 2), "q3": round(q3, 2),
                         "lower_fence": round(lo, 2), "upper_fence": round(hi, 2),
                         "flagged": int(flag.sum()),
                         "flagged_pct": round(100 * flag.sum() / n, 3) if n else ""})
    return pd.DataFrame(rows)


def scorecard(stage, t, ri, rules):
    rows = []
    for name in TABLES:
        df = t[name]
        # Completeness: missing cells where a value is expected (structural blanks excluded).
        # Missing = blank, whitespace-only or a placeholder token. The literal 'None' in
        # dim_advisor.certifications is NOT missing: it means "no certification" (D-04).
        allowed = expected_blank(t, name)
        expected_cells = (~allowed).values.sum()
        folded = df.apply(lambda s: s.str.strip().str.lower())
        missing = ((folded.isin(MISSING_TOKENS)) & ~allowed).values.sum()
        # Key uniqueness: rows whose primary key AND business key are unique
        dup = df[PKS[name]].duplicated(keep=False)
        if NATURAL_KEYS[name]:
            dup |= df.duplicated(NATURAL_KEYS[name], keep=False)
        # Type validity: non-blank typed cells in a strict, BI-readable format
        valid = total = 0
        for col, typ in TYPES[name].items():
            if col not in df.columns:
                continue
            v = df.loc[df[col] != "", col]
            total += len(v)
            valid += v.str.fullmatch(TYPE_PATTERNS[typ]).sum()
        r = rules[rules["table"] == name]
        ri_rows = ri[ri["child_table"] == name]
        non_null = (ri_rows["matched_non_null"] + ri_rows["orphan_rows"]).sum()
        rows.append({
            "table": name, "stage": stage, "rows": len(df),
            "pct_completeness": round(100 * (1 - missing / expected_cells), 3) if expected_cells else "",
            "pct_key_uniqueness": round(100 * (1 - dup.mean()), 3),
            "pct_type_validity": round(100 * valid / total, 3) if total else "",
            "pct_rule_pass": round(100 * (1 - r["failed"].sum() / r["evaluated"].sum()), 3)
            if r["evaluated"].sum() else "",
            "pct_referential_match": round(100 * ri_rows["matched_non_null"].sum() / non_null, 3)
            if non_null else "",
        })
    return pd.DataFrame(rows)


# ── Main ─────────────────────────────────────────────────────────────────────

def load(stage):
    return {n: pd.read_csv(STAGES[stage] / f"{n}.csv", dtype=str, keep_default_na=False) for n in TABLES}


def main():
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    raw = load("raw")
    results = {k: [] for k in ["ri", "rules", "recon", "outliers", "score"]}
    for stage in STAGES:
        t = raw if stage == "raw" else load(stage)
        ri = run_ri(stage, t)
        rules = run_rules(stage, t)
        results["ri"].append(ri)
        results["rules"].append(rules)
        results["recon"].append(run_reconciliations(stage, t, raw))
        results["outliers"].append(run_outliers(stage, t))
        results["score"].append(scorecard(stage, t, ri, rules))
    out = {k: pd.concat(v, ignore_index=True) for k, v in results.items()}

    score = out["score"].sort_values(["table", "stage"], key=lambda s: s.map(
        {"raw": 0, "clean": 1}) if s.name == "stage" else s).reset_index(drop=True)
    score.to_csv(REPORTS_DIR / "data_quality_scorecard.csv", index=False)
    out["ri"].to_csv(REPORTS_DIR / "ri_results.csv", index=False)
    out["rules"].to_csv(REPORTS_DIR / "rule_results.csv", index=False)
    out["recon"].to_csv(REPORTS_DIR / "reconciliations.csv", index=False)
    out["outliers"].to_csv(REPORTS_DIR / "outliers_iqr.csv", index=False)

    pd.set_option("display.width", 220)
    pd.set_option("display.max_colwidth", 70)
    print("=" * 70)
    print("HW4 PART D - VALIDATION (raw vs clean)")
    print("=" * 70)
    print("\nREFERENTIAL INTEGRITY")
    ri = out["ri"].pivot(index="relationship", columns="stage", values=["match_rate_pct", "orphan_rows"])
    print(ri.reindex(columns=["raw", "clean"], level=1).to_string())
    print("\nRULES THAT FAIL IN EITHER STAGE")
    rules = out["rules"].pivot_table(index=["table", "rule"], columns="stage", values="failed", aggfunc="sum")
    print(rules[(rules > 0).any(axis=1)].reindex(columns=["raw", "clean"]).to_string())
    print("\nRECONCILIATIONS")
    print(out["recon"][["stage", "reconciliation", "pass_pct", "result"]].to_string(index=False))
    print("\nIQR OUTLIERS (clean)")
    o = out["outliers"]
    print(o[o["stage"] == "clean"][["table", "column", "segment", "upper_fence", "flagged", "flagged_pct"]]
          .to_string(index=False))
    c = o[(o["stage"] == "clean") & (o["table"] == "dim_client")]
    overall = c.loc[c["segment"] == "(all)", "flagged_pct"].iloc[0]
    within_tier = c.loc[c["segment"] != "(all)", "flagged"].sum()
    print(f"Flagged does not mean wrong: wealth data is right-skewed, so the fences flag the large "
          f"accounts ({overall}% of initial_aum overall, but {within_tier} clients once fences are "
          f"set within each client tier), and flagged values still pass every business rule above.")
    print("\nDATA QUALITY SCORECARD")
    print(score.to_string(index=False))
    print(f"\nSaved scorecard + 4 detail files to {REPORTS_DIR.relative_to(HW_DIR)}")


if __name__ == "__main__":
    main()
