# 01_profile.py
# HW4 Part A: data-quality audit of the Wildcat Capital warehouse extract.
# Author: Jonah Karst
# Generated: 2026-10-25
#
# Two layers:
#   1. profile_table()  - generic column profiler; works on ANY csv with no
#                         configuration (null/blank, distinct, value shapes,
#                         parse failures, whitespace, mixed formats, min/max).
#   2. Rule checks       - generic check functions (type, allowed values, range,
#                         key uniqueness, duplicates, near-duplicates, row rules,
#                         referential integrity, cross-table rules). What to
#                         check is declared in the SPEC dictionaries below; the
#                         check code itself is never written for one table.
#
# Every file is read as text (dtype=str, keep_default_na=False) and converted
# on purpose inside each check. Raw files are never modified.
#
# Usage:
#   python hw04/scripts/01_profile.py                  # audit all 8 tables
#   python hw04/scripts/01_profile.py path/to/any.csv  # profile any csv(s)
#
# Outputs (full run):
#   hw04/reports/profile_raw.csv     one row per table x column
#   hw04/reports/dq_summary_raw.csv  one row per finding, tagged ERROR/WARN/INFO

import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HW_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = HW_DIR / "data" / "dirty"
REPORTS_DIR = HW_DIR / "reports"
PROFILE_PATH = REPORTS_DIR / "profile_raw.csv"
SUMMARY_PATH = REPORTS_DIR / "dq_summary_raw.csv"

# Literal strings that mean "missing" to a human or to default pandas parsing
NULL_TOKENS = {"none", "null", "nan", "n/a", "na", "-", "?", "missing"}

US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "DC", "FL", "GA", "HI", "ID",
    "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO",
    "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA",
    "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
}
ACCOUNT_TYPES = {"Taxable", "IRA", "Roth IRA", "Trust", "529"}

# ── Table specifications ────────────────────────────────────────────────────
# types:   int | decimal | date | bool | text   (expected type, not inferred)
# allowed: column -> set of valid codes
# ranges:  column -> (min, max), None = unbounded; (severity, reason)
TABLE_SPECS = {
    "dim_advisor": {
        "pk": "advisor_id",
        "types": {"advisor_id": "int", "years_experience": "int", "aum_target_mm": "int"},
        "allowed": {
            "region": {"Northeast", "Southeast", "Mid-Atlantic", "Midwest", "West"},
            "certifications": {"CFA", "CFP", "CFP, CFA", "CFP, CIMA", "None"},
        },
        "ranges": {"years_experience": (0, 60), "aum_target_mm": (0, None)},
    },
    "dim_benchmark": {
        "pk": "benchmark_id",
        "types": {"benchmark_id": "int"},
        "allowed": {},
        "ranges": {},
    },
    "dim_client": {
        "pk": "client_id",
        "types": {"client_id": "int", "age": "int", "zip_code": "text",
                  "initial_aum": "decimal", "client_since": "date",
                  "advisor_id": "int", "is_active": "bool"},
        "allowed": {
            "state": US_STATES,
            "risk_profile": {"Conservative", "Moderately Conservative", "Balanced",
                             "Moderately Aggressive", "Aggressive"},
            "client_tier": {"Retail", "HNW", "UHNW"},
            "primary_account_type": ACCOUNT_TYPES,
            "is_active": {"True", "False"},
        },
        "ranges": {"age": (18, 110), "initial_aum": (0, None),
                   "client_since": ("1990-01-01", "2024-12-31")},
        "patterns": {"zip_code": r"^\d{5}$"},
    },
    "dim_date": {
        "pk": "date_id",
        "types": {"date_id": "int", "date": "date", "year": "int", "quarter": "int",
                  "month": "int", "week_of_year": "int", "is_month_end": "int",
                  "is_quarter_end": "int", "is_year_end": "int", "is_trading_day": "int"},
        "allowed": {c: {"0", "1"} for c in
                    ["is_month_end", "is_quarter_end", "is_year_end", "is_trading_day"]},
        "ranges": {"quarter": (1, 4), "month": (1, 12), "week_of_year": (1, 53),
                   "date": ("2020-01-01", "2024-12-31")},
        "unique": ["date"],
    },
    "dim_security": {
        "pk": "security_id",
        "types": {"security_id": "int", "benchmark_id": "int", "is_etf": "bool",
                  "expense_ratio_bps": "decimal"},
        "allowed": {
            "asset_class": {"Equity", "Fixed Income", "Alternative", "Cash Equivalent"},
            "is_etf": {"True", "False"},
        },
        "ranges": {"expense_ratio_bps": (0, 300)},
        "unique": ["ticker"],
    },
    "fact_fees": {
        "pk": "fee_id",
        "types": {"fee_id": "int", "client_id": "int", "advisor_id": "int",
                  "fee_date": "date", "aum_basis": "decimal",
                  "bps_charged": "decimal", "amount": "decimal"},
        "allowed": {"fee_type": {"Management", "Advisory", "Custodial", "Performance"}},
        # Fee schedule assumption: no fee above 100 bps (1%) of AUM per year
        "ranges": {"aum_basis": (0, None), "bps_charged": (0, 100), "amount": (0, None),
                   "fee_date": ("2020-01-01", "2024-12-31")},
        "grain": ["client_id", "fee_date", "fee_type"],
    },
    "fact_portfolio_snapshot": {
        "pk": "snapshot_id",
        "types": {"snapshot_id": "int", "client_id": "int", "advisor_id": "int",
                  "benchmark_id": "int", "snapshot_date": "date", "year": "int",
                  "month": "int", "aum": "decimal", "return_ytd": "decimal",
                  "benchmark_return_ytd": "decimal", "active_alpha_ytd": "decimal",
                  "cash_pct": "decimal"},
        "allowed": {"account_type": ACCOUNT_TYPES},
        # A return below -100% is impossible; above +100% YTD is a plausibility flag
        "ranges": {"aum": (0, None), "cash_pct": (0, 1), "month": (1, 12),
                   "return_ytd": (-1, None), "snapshot_date": ("2020-01-01", "2024-12-31")},
        "soft_ranges": {"return_ytd": (-0.9, 1.0)},
        "grain": ["client_id", "snapshot_date"],
    },
    "fact_transactions": {
        "pk": "txn_id",
        "types": {"txn_id": "int", "client_id": "int", "advisor_id": "int",
                  "security_id": "int", "txn_date": "date", "shares": "decimal",
                  "price": "decimal", "amount": "decimal"},
        "allowed": {"txn_type": {"Buy", "Sell", "Dividend", "Deposit",
                                 "Withdrawal", "Advisory Fee"}},
        "ranges": {"price": (0, None), "amount": (0, None),
                   "txn_date": ("2020-01-01", "2024-12-31")},
    },
}

# ── Relationships (fact/child column -> dimension key) ──────────────────────
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

findings = []


def add_finding(group, table, column, check, severity, rows, total, example="", detail=""):
    """Record one data-quality finding (only called when something was found)."""
    findings.append({
        "check_group": group,
        "table": table,
        "column": column,
        "check": check,
        "severity": severity,
        "rows_affected": int(rows),
        "pct_affected": round(100 * rows / total, 3) if total else 0.0,
        "example": str(example)[:120],
        "detail": detail,
    })


def log(line=""):
    print(line)


# ── Value classification helpers ─────────────────────────────────────────────

RE_INT = re.compile(r"^-?\d+$")
RE_INT_AS_FLOAT = re.compile(r"^-?\d+\.0+$")
RE_DECIMAL = re.compile(r"^-?\d*\.\d+$")
RE_SCIENTIFIC = re.compile(r"^-?\d*\.?\d+[eE][-+]?\d+$")
RE_PERCENT = re.compile(r"^-?\d*\.?\d+\s*%$")
RE_CURRENCY = re.compile(r"^-?\$\s?[\d,]*\.?\d+$")
RE_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
RE_OTHER_DATE = re.compile(r"^\d{1,2}[/-]\d{1,2}[/-]\d{2,4}$")
BOOL_TOKENS = {"true", "false", "yes", "no", "y", "n"}


def value_shape(v):
    """Shape of a value: letters -> A, digits -> 9 (e.g. '03897' -> '99999')."""
    if v == "":
        return "<blank>"
    return re.sub(r"\d", "9", re.sub(r"[A-Za-z]", "A", v))


def shape_family(shape):
    """Collapse runs so '999.99' and '9.9' are one family; used for mixed-format detection."""
    fam = re.sub(r"A+", "A", re.sub(r"9+", "9", shape.lstrip("-")))
    return "9" if fam == "9.9" else fam  # whole numbers and decimals are one numeric format


def classify(v):
    """Assign one format class to a non-blank text value."""
    s = v.strip()
    if RE_INT.match(s):
        return "int"
    if RE_INT_AS_FLOAT.match(s):
        return "int_as_float"
    if RE_DECIMAL.match(s):
        return "decimal"
    if RE_SCIENTIFIC.match(s):
        return "scientific"
    if RE_PERCENT.match(s):
        return "percent"
    if RE_CURRENCY.match(s):
        return "currency"
    if RE_ISO_DATE.match(s):
        return "date"
    if RE_OTHER_DATE.match(s):
        return "date_other"
    if s.lower() in BOOL_TOKENS:
        return "bool"
    return "text"


# Which format classes count as a clean parse for each expected type
PARSES_AS = {
    "int": {"int"},
    "decimal": {"int", "int_as_float", "decimal", "scientific"},
    "date": {"date"},
    "bool": {"bool"},
    "text": None,  # anything parses as text
}


def infer_type(class_counts):
    """Expected type when no spec is given: dominant class among non-blank values."""
    if class_counts.empty:
        return "text"
    top = class_counts.idxmax()
    if top in ("int", "int_as_float"):
        # whole numbers alongside decimals are still a decimal column
        return "decimal" if class_counts.get("decimal", 0) > 0 else "int"
    if top in ("decimal", "scientific", "percent", "currency"):
        return "decimal"
    if top in ("date", "date_other"):
        return "date"
    return top if top in PARSES_AS else "text"


def to_number(series):
    """Strict numeric conversion of a text column; anything non-numeric becomes NaN."""
    return pd.to_numeric(series.where(series.str.strip() != ""), errors="coerce")


def to_date(series):
    return pd.to_datetime(series.where(series != ""), format="%Y-%m-%d", errors="coerce")


# ── 1. Generic column profiler ──────────────────────────────────────────────

def profile_table(df, table, spec=None):
    """Profile every column of any DataFrame read as text. Returns one row per column."""
    spec = spec or {}
    rows = []
    n = len(df)
    for col in df.columns:
        s = df[col]
        blank = s.str.strip() == ""
        null_token = s.str.strip().str.lower().isin(NULL_TOKENS)
        non_blank = s[~blank]

        value_shapes = s.map(value_shape)
        shapes = value_shapes.value_counts()
        top_shapes = "; ".join(f"{k} ({100 * v / n:.1f}%)" for k, v in shapes.head(3).items())
        families = value_shapes[~blank].map(shape_family).value_counts()

        value_class = non_blank.map(classify)
        classes = value_class.value_counts()
        inferred = infer_type(classes)
        expected = spec.get("types", {}).get(col, inferred)
        ok_classes = PARSES_AS[expected]
        if ok_classes is None:
            fail = 0
            fail_examples = []
        else:
            failed = ~value_class.isin(ok_classes)
            fail = int(failed.sum())
            fail_examples = non_blank[failed].unique()[:3].tolist()

        lead_trail = int((s != s.str.strip()).sum())
        double_space = int(s.str.contains(r"\s{2,}", regex=True).sum())
        # values that collide after trimming / case-folding (e.g. 'PA' vs 'pa ')
        folded = non_blank.str.strip().str.lower()
        case_variants = int(non_blank.nunique() - folded.nunique())

        nums = to_number(s) if expected in ("int", "decimal") else pd.Series(dtype=float)
        if expected == "date":
            dates = to_date(s)
            vmin, vmax = dates.min(), dates.max()
            vmin = "" if pd.isna(vmin) else vmin.date().isoformat()
            vmax = "" if pd.isna(vmax) else vmax.date().isoformat()
        elif nums.notna().any():
            vmin, vmax = nums.min(), nums.max()
        else:
            vmin = vmax = ""

        top_vals = s.value_counts().head(3)
        rows.append({
            "table": table,
            "column": col,
            "rows": n,
            "blank_count": int(blank.sum()),
            "null_token_count": int(null_token.sum()),
            "blank_pct": round(100 * blank.sum() / n, 3) if n else 0.0,
            "distinct_count": int(s.nunique()),
            "distinct_pct": round(100 * s.nunique() / n, 3) if n else 0.0,
            "inferred_type": inferred,
            "expected_type": expected,
            "parse_fail_count": fail,
            "parse_fail_pct": round(100 * fail / len(non_blank), 3) if len(non_blank) else 0.0,
            "parse_fail_examples": " | ".join(map(str, fail_examples)),
            "format_classes": "; ".join(f"{k}={v}" for k, v in classes.items()),
            "shape_families": int(len(families)),
            "minority_format_count": int(families.iloc[1:].sum()),
            "top_shapes": top_shapes,
            "lead_trail_ws": lead_trail,
            "double_space": double_space,
            "case_variants": case_variants,
            "min": vmin,
            "max": vmax,
            "top_values": "; ".join(f"{k!r}={v}" for k, v in top_vals.items()),
        })
    return pd.DataFrame(rows)


def findings_from_profile(prof):
    """Turn profile metrics into column-level findings (applies to any table)."""
    for _, p in prof.iterrows():
        t, c, n = p["table"], p["column"], p["rows"]
        if p["blank_count"]:
            add_finding("1_column", t, c, "blank values", "INFO", p["blank_count"], n,
                        detail="Blank cells; decide in decision log whether structural or a defect")
        if p["null_token_count"]:
            add_finding("1_column", t, c, "null-like text token", "WARN", p["null_token_count"], n,
                        example=p["top_values"],
                        detail="Text such as 'None' becomes NaN under default parsing")
        if p["parse_fail_count"]:
            sev = "ERROR"
            add_finding("1_column", t, c, f"fails to parse as {p['expected_type']}", sev,
                        p["parse_fail_count"], n, example=p["parse_fail_examples"],
                        detail=f"Format classes: {p['format_classes']}")
        if p["shape_families"] > 1 and p["expected_type"] != "text":
            add_finding("1_column", t, c, "mixed formats", "WARN", p["minority_format_count"], n,
                        example=p["top_shapes"],
                        detail=f"{p['shape_families']} distinct value-shape families in a typed column")
        if p["lead_trail_ws"] or p["double_space"]:
            add_finding("1_column", t, c, "whitespace problems", "WARN",
                        p["lead_trail_ws"] + p["double_space"], n)
        if p["case_variants"]:
            add_finding("1_column", t, c, "case/whitespace variants of same value", "WARN",
                        p["case_variants"], n)


# ── 2. Column-level rule checks ─────────────────────────────────────────────

def check_columns(df, table, spec):
    n = len(df)
    pk = spec.get("pk")
    for key in [pk] + spec.get("unique", []):
        if key is None:
            continue
        dup = df[key].duplicated(keep=False) & (df[key] != "")
        if dup.any():
            add_finding("1_column", table, key, "key not unique", "ERROR", dup.sum(), n,
                        example=df.loc[dup, key].iloc[0])
        if (df[key] == "").any():
            add_finding("1_column", table, key, "blank key", "ERROR", (df[key] == "").sum(), n)

    for col, allowed in spec.get("allowed", {}).items():
        vals = df[col]
        bad = (vals != "") & ~vals.isin(allowed)
        if bad.any():
            add_finding("1_column", table, col, "value not in allowed list", "ERROR", bad.sum(), n,
                        example=vals[bad].value_counts().head(5).to_dict())

    for col, pattern in spec.get("patterns", {}).items():
        bad = (df[col] != "") & ~df[col].str.match(pattern)
        if bad.any():
            add_finding("1_column", table, col, f"does not match pattern {pattern}", "ERROR",
                        bad.sum(), n, example=df.loc[bad, col].iloc[0])

    for col, (lo, hi) in spec.get("ranges", {}).items():
        if spec["types"].get(col) == "date":
            # unparseable dates are already reported as parse failures; skip them here
            vals, lo_v, hi_v = to_date(df[col]), pd.Timestamp(lo), pd.Timestamp(hi)
            ok = vals.notna()
        else:
            vals, lo_v, hi_v = to_number(df[col]), lo, hi
            ok = vals.notna()
        out = pd.Series(False, index=df.index)
        if lo_v is not None:
            out |= ok & (vals < lo_v)
        if hi_v is not None:
            out |= ok & (vals > hi_v)
        if out.any():
            add_finding("1_column", table, col, f"outside valid range [{lo}, {hi}]", "ERROR",
                        out.sum(), n, example=df.loc[out, col].iloc[0])

    for col, (lo, hi) in spec.get("soft_ranges", {}).items():
        vals = to_number(df[col])
        out = (vals < lo) | (vals > hi)
        if out.any():
            add_finding("1_column", table, col, f"implausible value outside [{lo}, {hi}]", "WARN",
                        out.sum(), n, example=df.loc[out, col].iloc[0])

    # Generic: one exact value repeated far more than any other in a high-cardinality
    # numeric column is a likely placeholder/default (e.g. 1000.0 standing in for unknown)
    for col, typ in spec.get("types", {}).items():
        if typ != "decimal":
            continue
        spike = value_spike(df[col])
        if spike:
            value, count, runner_up = spike
            add_finding("1_column", table, col, "value spike (possible placeholder)", "WARN",
                        count, n, example=value,
                        detail=f"'{value}' appears {count}x; next most common {runner_up}x")


def value_spike(series):
    """(value, count, runner-up count) if one value dominates a high-cardinality column, else None."""
    vc = series[series != ""].value_counts()
    if len(vc) > 100 and vc.iloc[0] >= 20 * max(vc.iloc[1], 1):
        return vc.index[0], int(vc.iloc[0]), int(vc.iloc[1])
    return None


# ── 3. Single-table rules ───────────────────────────────────────────────────

def check_duplicates(df, table, spec):
    """Exact duplicates (ignoring the surrogate key), grain duplicates, near-duplicates."""
    n = len(df)
    pk = spec.get("pk")
    body = df.drop(columns=[pk]) if pk else df
    dup = body.duplicated(keep=False)
    if dup.any():
        add_finding("2_single_table", table, "*", "exact duplicate rows (excluding key)", "ERROR",
                    dup.sum(), n)

    grain = spec.get("grain")
    if grain:
        g = df.duplicated(grain, keep=False)
        if g.any():
            add_finding("2_single_table", table, "+".join(grain), "duplicate at business grain",
                        "ERROR", g.sum(), n)

    # Near-duplicate: identical on every column except the key and ONE other column.
    # Only meaningful for dimensions (entities); in facts, coincidental matches are common.
    if table.startswith("dim_") and len(body.columns) >= 4:
        for col in body.columns:
            rest = body.drop(columns=[col])
            nd = rest.duplicated(keep=False) & ~dup
            if nd.any():
                pairs = df.loc[nd].sort_values(list(rest.columns))
                ex = pairs[[pk, col]].head(2).values.tolist() if pk else ""
                add_finding("2_single_table", table, col,
                            f"near-duplicate rows (all columns match except {col})", "ERROR",
                            nd.sum(), n, example=ex,
                            detail=f"{nd.sum() // 2} pairs; same entity entered twice?")


def row_rule(df, table, column, name, severity, failed, detail=""):
    """Record a row-level rule; `failed` is a boolean mask of violating rows."""
    if failed.any():
        add_finding("2_single_table", table, column, name, severity, failed.sum(), len(df),
                    example=df.index[failed][0], detail=detail)


def check_row_rules(t):
    """Values that contradict other columns of the same row."""
    # Transactions: security fields must be present exactly for security-level txn types
    tx = t["fact_transactions"]
    # Case/whitespace-insensitive so a dirty "buy " is still treated as a security txn
    # (the variant itself is reported by the allowed-values check)
    sec_types = {"buy", "sell", "dividend"}
    is_sec = tx["txn_type"].str.strip().str.lower().isin(sec_types)
    for col in ["security_id", "shares", "price"]:
        row_rule(tx, "fact_transactions", col, f"{col} blank on Buy/Sell/Dividend", "ERROR",
                 is_sec & (tx[col] == ""))
        row_rule(tx, "fact_transactions", col, f"{col} filled on cash-only txn type", "ERROR",
                 ~is_sec & (tx[col] != ""))
    blank_cash = (~is_sec & (tx["security_id"] == "")).sum()
    add_finding("2_single_table", "fact_transactions", "security_id/shares/price",
                "blank by design on Deposit/Withdrawal/Advisory Fee", "INFO", blank_cash, len(tx),
                detail="Structural: cash movements have no security; not a defect")
    shares, price, amount = (to_number(tx[c]) for c in ["shares", "price", "amount"])
    row_rule(tx, "fact_transactions", "shares", "shares <= 0 on security txn", "ERROR",
             is_sec & (shares <= 0), detail="Sign rule: share counts are positive; txn_type carries direction")
    recon = (shares * price - amount).abs()
    row_rule(tx, "fact_transactions", "amount", "amount != shares x price (tol 0.01)", "ERROR",
             is_sec & (recon > 0.01))
    recon_abs = (shares.abs() * price - amount).abs()
    row_rule(tx, "fact_transactions", "shares", "|shares| x price = amount (sign-only error)", "INFO",
             is_sec & (recon > 0.01) & (recon_abs <= 0.01),
             detail="Amount reconciles once shares sign is flipped: repair is verifiable")

    # Fees: amount = aum_basis x bps / 10,000 / 12 (monthly)
    fee = t["fact_fees"]
    calc = to_number(fee["aum_basis"]) * to_number(fee["bps_charged"]) / 10000 / 12
    row_rule(fee, "fact_fees", "amount", "amount != aum_basis x bps / 120,000 (tol 0.01)", "ERROR",
             (calc - to_number(fee["amount"])).abs() > 0.01)

    # Snapshots: alpha = return - benchmark; year/month agree with snapshot_date
    snap = t["fact_portfolio_snapshot"]
    ret = to_number(snap["return_ytd"].str.rstrip("%"))
    ret = ret.where(~snap["return_ytd"].str.endswith("%"), ret / 100)
    alpha_gap = (ret - to_number(snap["benchmark_return_ytd"]) - to_number(snap["active_alpha_ytd"])).abs()
    row_rule(snap, "fact_portfolio_snapshot", "active_alpha_ytd",
             "alpha != return_ytd - benchmark_return_ytd (tol 1e-4)", "ERROR", alpha_gap > 1e-4,
             detail="return_ytd percent strings divided by 100 before comparing")
    pct = snap["return_ytd"].str.endswith("%")
    row_rule(snap, "fact_portfolio_snapshot", "return_ytd",
             "percent string reconciles to alpha after /100", "INFO", pct & (alpha_gap <= 1e-4),
             detail="Unit repair is verifiable against benchmark and alpha columns")
    # Unparseable dates are reported as parse failures; exclude them so one bad
    # date does not also count as a derived-field disagreement
    d = to_date(snap["snapshot_date"])
    parsed = d.notna()
    row_rule(snap, "fact_portfolio_snapshot", "year/month", "year/month disagree with snapshot_date",
             "ERROR", parsed & ((d.dt.year != to_number(snap["year"])) |
                                (d.dt.month != to_number(snap["month"]))))
    row_rule(snap, "fact_portfolio_snapshot", "snapshot_date", "snapshot not on 1st of month", "WARN",
             parsed & (d.dt.day != 1))

    # Dates: derived attributes agree with the date itself
    dd = t["dim_date"]
    dt = to_date(dd["date"])
    derived = {
        "year": dt.dt.year, "quarter": dt.dt.quarter, "month": dt.dt.month,
        "week_of_year": dt.dt.isocalendar().week.astype(float),
        "is_month_end": dt.dt.is_month_end.astype(int), "is_quarter_end": dt.dt.is_quarter_end.astype(int),
        "is_year_end": dt.dt.is_year_end.astype(int),
    }
    for col, expected in derived.items():
        row_rule(dd, "dim_date", col, f"{col} disagrees with date", "ERROR",
                 dt.notna() & (to_number(dd[col]) != expected))
    row_rule(dd, "dim_date", "month_name", "month_name disagrees with date", "ERROR",
             dt.notna() & (dd["month_name"] != dt.dt.month_name()))
    row_rule(dd, "dim_date", "day_of_week", "day_of_week disagrees with date", "ERROR",
             dt.notna() & (dd["day_of_week"] != dt.dt.day_name()))
    row_rule(dd, "dim_date", "is_trading_day", "weekend marked as trading day", "ERROR",
             (dt.dt.dayofweek >= 5) & (dd["is_trading_day"] == "1"))
    gaps = dt.sort_values().diff().dt.days.dropna()
    row_rule(dd, "dim_date", "date", "calendar gap (missing day)", "ERROR", gaps.reindex(dd.index) > 1)

    # Securities: ETFs carry an expense ratio and no sector; single stocks the reverse
    sec = t["dim_security"]
    etf = sec["is_etf"] == "True"
    row_rule(sec, "dim_security", "expense_ratio_bps", "ETF missing expense ratio", "ERROR",
             etf & (sec["expense_ratio_bps"] == ""))
    row_rule(sec, "dim_security", "expense_ratio_bps", "non-ETF has expense ratio", "WARN",
             ~etf & (sec["expense_ratio_bps"] != ""))
    row_rule(sec, "dim_security", "sector", "non-ETF missing sector", "ERROR",
             ~etf & (sec["sector"] == ""))
    add_finding("2_single_table", "dim_security", "sector/expense_ratio_bps",
                "blank by design (sector on ETFs, expense ratio on non-ETFs)", "INFO",
                (etf & (sec["sector"] == "")).sum() + (~etf & (sec["expense_ratio_bps"] == "")).sum(),
                len(sec), detail="Structural: each blank aligns exactly with is_etf")
    multi = sec.groupby("asset_class")["benchmark_id"].nunique()
    if (multi > 1).any():
        add_finding("2_single_table", "dim_security", "benchmark_id",
                    "asset_class maps to more than one benchmark", "INFO", int((multi > 1).sum()),
                    sec["asset_class"].nunique(), example=multi[multi > 1].to_dict())

    # Clients: tier should match initial AUM band (Retail < $500K <= HNW < $5M <= UHNW)
    cl = t["dim_client"]
    aum = to_number(cl["initial_aum"])
    band = np.select([aum < 500_000, aum < 5_000_000], ["Retail", "HNW"], "UHNW")
    row_rule(cl, "dim_client", "client_tier", "tier disagrees with initial_aum band", "WARN",
             aum.notna() & (cl["client_tier"] != band))
    row_rule(cl, "dim_client", "age", "client under 18 at client_since", "ERROR",
             to_number(cl["age"]) - (2024 - to_date(cl["client_since"]).dt.year) < 18,
             detail="Assumes age is as of the 2024 extract")


# ── 4. Referential integrity ────────────────────────────────────────────────

def check_relationships(t):
    for child, fk, parent, pk in RELATIONSHIPS:
        c = t[child]
        n = len(c)
        keys = c[fk]
        nonblank = keys != ""
        parent_keys = set(t[parent][pk])
        orphan = nonblank & ~keys.isin(parent_keys)
        name = f"{child}.{fk} -> {parent}.{pk}"
        if orphan.any():
            # Is it a real orphan, or a format mismatch that breaks a text join?
            norm = keys.str.replace(r"\.0+$", "", regex=True)
            true_orphan = nonblank & ~norm.isin(parent_keys)
            if true_orphan.sum() < orphan.sum():
                add_finding("3_referential", child, fk, f"FK format breaks join: {name}", "ERROR",
                            (orphan & ~true_orphan).sum(), n, example=keys[orphan & ~true_orphan].iloc[0],
                            detail="Key matches only after removing trailing '.0' (int stored as float)")
            if true_orphan.any():
                add_finding("3_referential", child, fk, f"orphan FK: {name}", "ERROR",
                            true_orphan.sum(), n, example=keys[true_orphan].iloc[0],
                            detail=f"{keys[true_orphan].nunique()} distinct keys not in {parent}")
        else:
            add_finding("3_referential", child, fk, f"RI ok: {name}", "INFO", 0, n,
                        detail="100% match")
        if (~nonblank).any():
            add_finding("3_referential", child, fk, f"null FK: {name}", "INFO", (~nonblank).sum(), n)

    # Dimension members never referenced by any fact
    used = {}
    for child, fk, parent, pk in RELATIONSHIPS:
        if child.startswith("fact_") or parent == "dim_benchmark":
            used.setdefault((parent, pk), set()).update(
                t[child][fk].str.replace(r"\.0+$", "", regex=True))
    for (parent, pk), keys in used.items():
        unused = ~t[parent][pk].isin(keys)
        if unused.any() and parent != "dim_date":
            add_finding("3_referential", parent, pk, "dimension members with no fact rows", "WARN",
                        unused.sum(), len(t[parent]),
                        example=t[parent].loc[unused, pk].head(5).tolist())


# ── 5. Cross-table business rules ───────────────────────────────────────────

def check_cross_table(t):
    cl = t["dim_client"]
    # One row per key before merging: a duplicated PK (reported by the key check)
    # must not multiply fact rows and inflate counts here
    client_cols = cl[["client_id", "advisor_id", "primary_account_type", "client_since",
                      "is_active"]].drop_duplicates("client_id")

    # Fact advisor must equal the client's advisor in dim_client
    for fact in ["fact_fees", "fact_portfolio_snapshot", "fact_transactions"]:
        f = t[fact]
        m = f[["client_id", "advisor_id"]].merge(client_cols, on="client_id", how="left",
                                                 suffixes=("", "_dim"))
        bad = m["advisor_id_dim"].notna() & (m["advisor_id"] != m["advisor_id_dim"])
        if bad.any():
            add_finding("4_cross_table", fact, "advisor_id", "advisor differs from dim_client.advisor_id",
                        "WARN", bad.sum(), len(f))

    # Snapshot account_type must equal client's primary_account_type
    snap = t["fact_portfolio_snapshot"]
    m = snap[["client_id", "account_type"]].merge(client_cols, on="client_id", how="left")
    bad = m["primary_account_type"].notna() & (m["account_type"] != m["primary_account_type"])
    if bad.any():
        add_finding("4_cross_table", "fact_portfolio_snapshot", "account_type",
                    "account_type differs from dim_client.primary_account_type", "WARN", bad.sum(), len(snap))

    # Activity before the client relationship started
    # Monthly facts are dated the 1st, so they compare to the start month;
    # daily transactions compare to the exact start date
    for fact, dcol, monthly in [("fact_fees", "fee_date", True),
                                ("fact_portfolio_snapshot", "snapshot_date", True),
                                ("fact_transactions", "txn_date", False)]:
        f = t[fact]
        m = f[["client_id", dcol]].merge(client_cols, on="client_id", how="left")
        start = to_date(m["client_since"])
        if monthly:
            start = start.dt.to_period("M").dt.to_timestamp()
        bad = to_date(m[dcol]) < start
        if bad.any():
            add_finding("4_cross_table", fact, dcol, "activity before client_since", "ERROR",
                        bad.sum(), len(f))

    # Fee basis must equal the same client's snapshot AUM for that month
    fee = t["fact_fees"]
    snap_grain = snap[["client_id", "snapshot_date", "aum"]].drop_duplicates(["client_id", "snapshot_date"])
    m = fee.merge(snap_grain, left_on=["client_id", "fee_date"],
                  right_on=["client_id", "snapshot_date"], how="left")
    no_snap = m["aum"].isna()
    if no_snap.any():
        add_finding("4_cross_table", "fact_fees", "fee_date", "fee with no snapshot that month", "WARN",
                    no_snap.sum(), len(fee))
    gap = (to_number(m["aum_basis"]) - to_number(m["aum"].fillna(""))).abs() > 0.01
    if gap.any():
        add_finding("4_cross_table", "fact_fees", "aum_basis", "aum_basis != snapshot aum", "ERROR",
                    gap.sum(), len(fee))
    else:
        add_finding("4_cross_table", "fact_fees", "aum_basis", "aum_basis reconciles to snapshot aum",
                    "INFO", 0, len(fee), detail="Fees and snapshots agree; usable to verify AUM repairs")
    fee_spike, snap_spike = value_spike(fee["aum_basis"]), value_spike(snap["aum"])
    if fee_spike and snap_spike and fee_spike[0] == snap_spike[0]:
        v = fee_spike[0]
        both = ((m["aum_basis"] == v) & (m["aum"] == v)).sum()
        add_finding("4_cross_table", "fact_fees", "aum_basis",
                    f"placeholder {v} in aum_basis mirrors snapshot aum", "WARN", both, len(fee),
                    detail=f"Same client-month holds {v} in both tables; cannot be verified from either")

    # Inactive clients should not keep generating activity
    inactive = set(cl.loc[cl["is_active"] == "False", "client_id"])
    last_snap = snap[snap["client_id"].isin(inactive)].groupby("client_id")["snapshot_date"].max()
    tx = t["fact_transactions"]
    m = tx[tx["client_id"].isin(inactive)].merge(last_snap.rename("last_snap"), on="client_id")
    late = m["txn_date"] > m["last_snap"].str[:8] + "31"
    if late.any():
        add_finding("4_cross_table", "fact_transactions", "txn_date",
                    "inactive client transacts after last snapshot", "WARN", late.sum(), len(tx))
    active_ids = set(cl.loc[cl["is_active"] == "True", "client_id"])
    snap_dates = to_date(snap["snapshot_date"])
    max_snap = snap_dates.max()
    last_all = snap_dates.groupby(snap["client_id"]).max()
    stale = last_all[last_all.index.isin(active_ids) & (last_all < max_snap)]
    if len(stale):
        add_finding("4_cross_table", "dim_client", "is_active",
                    "active client with no snapshot in final month", "WARN", len(stale), len(cl))
    early = last_all[last_all.index.isin(inactive) & (last_all == max_snap)]
    if len(early):
        add_finding("4_cross_table", "dim_client", "is_active",
                    "inactive client still has final-month snapshot", "WARN", len(early), len(cl))

    # Trades (Buy/Sell) dated on non-trading days per dim_date
    dd = t["dim_date"][["date", "is_trading_day"]]
    m = tx[["txn_type", "txn_date"]].merge(dd, left_on="txn_date", right_on="date", how="left")
    off = m["txn_type"].isin({"Buy", "Sell"}) & (m["is_trading_day"] == "0")
    if off.any():
        add_finding("4_cross_table", "fact_transactions", "txn_date",
                    "Buy/Sell on a non-trading day (dim_date)", "WARN", off.sum(), len(tx))

    # Snapshot benchmark vs. dimension usage
    unused_bm = set(t["dim_benchmark"]["benchmark_id"]) - set(snap["benchmark_id"]) - \
        set(t["dim_security"]["benchmark_id"])
    if unused_bm:
        add_finding("4_cross_table", "dim_benchmark", "benchmark_id",
                    "benchmark not used by any snapshot or security", "INFO", len(unused_bm),
                    len(t["dim_benchmark"]), example=sorted(unused_bm))

    # client_since precedes the calendar in dim_date: expected, not an RI failure
    pre = (to_date(cl["client_since"]) < to_date(t["dim_date"]["date"]).min()).sum()
    if pre:
        add_finding("4_cross_table", "dim_client", "client_since",
                    "client_since earlier than dim_date coverage", "INFO", pre, len(cl),
                    detail="Not a date-table FK: dim_date covers the 2020-2024 fact period only")


# ── Main ─────────────────────────────────────────────────────────────────────

def read_raw(path):
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def profile_only(paths):
    """Ad-hoc mode: generic profile of any csv files, no business rules."""
    for p in paths:
        df = read_raw(p)
        prof = profile_table(df, Path(p).stem)
        log(f"\n=== {p}  ({len(df):,} rows x {df.shape[1]} cols) ===")
        with pd.option_context("display.width", 200, "display.max_columns", None):
            log(prof[["column", "blank_count", "distinct_count", "expected_type",
                      "parse_fail_count", "shape_families", "min", "max"]].to_string(index=False))


def main():
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    tables = {name: read_raw(RAW_DIR / f"{name}.csv") for name in TABLE_SPECS}

    log("=" * 70)
    log("HW4 PART A - DATA QUALITY AUDIT (raw)")
    log("=" * 70)
    for name, df in tables.items():
        log(f"  {name:<26} {len(df):>9,} rows  {df.shape[1]:>3} cols")

    profiles = []
    for name, df in tables.items():
        spec = TABLE_SPECS[name]
        prof = profile_table(df, name, spec)
        profiles.append(prof)
        findings_from_profile(prof)
        check_columns(df, name, spec)
        check_duplicates(df, name, spec)
    check_row_rules(tables)
    check_relationships(tables)
    check_cross_table(tables)

    profile = pd.concat(profiles, ignore_index=True)
    profile.to_csv(PROFILE_PATH, index=False)

    sev_order = {"ERROR": 0, "WARN": 1, "INFO": 2}
    summary = pd.DataFrame(findings)
    summary = summary.sort_values(["severity", "check_group", "table", "rows_affected"],
                                  key=lambda s: s.map(sev_order) if s.name == "severity" else s,
                                  ascending=[True, True, True, False]).reset_index(drop=True)
    summary.insert(0, "finding_id", [f"F{i + 1:03d}" for i in range(len(summary))])
    summary.to_csv(SUMMARY_PATH, index=False)

    log("\nFINDINGS BY SEVERITY AND CHECK GROUP")
    log(pd.crosstab(summary["check_group"], summary["severity"]).to_string())
    log("\nERROR AND WARN FINDINGS")
    with pd.option_context("display.width", 220, "display.max_colwidth", 60):
        cols = ["finding_id", "severity", "table", "column", "check", "rows_affected", "pct_affected"]
        log(summary.loc[summary["severity"] != "INFO", cols].to_string(index=False))
    log(f"\nSaved {PROFILE_PATH.relative_to(HW_DIR)} ({len(profile)} rows)")
    log(f"Saved {SUMMARY_PATH.relative_to(HW_DIR)} ({len(summary)} findings)")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        profile_only(sys.argv[1:])
    else:
        main()
