# 03_measures.py
# HW5 Part C: classify every numeric column in the Wildcat Capital fact tables
# as additive, semi-additive or non-additive, separate the numeric columns that
# are not measures, and list the numeric dimension attributes never to sum.
# Author: Jonah Karst
# Generated: 2026-11-01
#
# The classification is declared in FACT_COLUMNS and DIM_COLUMNS. The script:
#   1. Coverage    finds every numeric column in the data (including columns
#                  that are mostly numeric with stray text) and fails if one is
#                  unclassified, or a classified column is not fully numeric
#   2. Evidence    tests the arithmetic each classification rests on, on every
#                  row (a blank or unparseable value fails, it is not skipped):
#                  fee = AUM x bps / 10,000 / 12, aum_basis = snapshot aum,
#                  YTD returns reset in January, alpha = return - benchmark,
#                  trade amount = shares x price, amounts always positive, ...
#   3. Totals      shows what goes wrong when a balance is summed across months
#
# Figures quoted in star_design.md Part C are pinned in EXPECTED, and the
# tolerances it quotes in TOLERANCES.
#
# Usage:  python hw05/scripts/03_measures.py
#
# Output (hw05/reports/):
#   measures.csv   one row per numeric column (facts and dimensions)

import pandas as pd

from common import REPORTS_DIR, Checks, is_blank, load_tables, parse_iso_date

ADD, SEMI, NON = "additive", "semi-additive", "non-additive"
KEY, DATE_PART, FLAG = "key", "date part", "flag"

# (role, how it may be aggregated)
FACT_COLUMNS = {
    "fact_fees": {
        "fee_id": (KEY, "count rows; never sum"),
        "client_id": (KEY, "foreign key; never sum"),
        "advisor_id": (KEY, "foreign key; never sum"),
        "aum_basis": (SEMI, "sum across clients within one month; across months use the last or average month"),
        "bps_charged": (NON, "never sum; effective rate = SUM(amount) x 12 x 10,000 / SUM(aum_basis)"),
        "amount": (ADD, "sum across clients, advisors, fee types and months"),
    },
    "fact_portfolio_snapshot": {
        "snapshot_id": (KEY, "count rows; never sum"),
        "client_id": (KEY, "foreign key; never sum"),
        "advisor_id": (KEY, "foreign key; never sum"),
        "benchmark_id": (KEY, "foreign key; never sum"),
        "year": (DATE_PART, "part of snapshot_date; group by, never sum"),
        "month": (DATE_PART, "part of snapshot_date; group by, never sum"),
        "aum": (SEMI, "sum across clients within one month; across months use the last or average month"),
        "return_ytd": (NON, "never sum; latest month of the year, AUM-weighted across clients"),
        "benchmark_return_ytd": (NON, "never sum; one value per benchmark-month, repeated on every client"),
        "active_alpha_ytd": (NON, "never sum; = return_ytd - benchmark_return_ytd, aggregate those first"),
        "cash_pct": (NON, "never sum; AUM-weighted: SUM(aum x cash_pct) / SUM(aum)"),
        "is_return_suspect": (FLAG, "0/1 flag; count flagged rows, never treat as a measure"),
    },
    "fact_transactions": {
        "txn_id": (KEY, "count rows; never sum"),
        "client_id": (KEY, "foreign key; never sum"),
        "advisor_id": (KEY, "foreign key; never sum"),
        "security_id": (KEY, "foreign key; never sum"),
        "shares": (SEMI, "sum only within one security and one txn_type; never across securities"),
        "price": (NON, "never sum; average trade price = SUM(amount) / SUM(shares) over Buy/Sell of one security"),
        "amount": (SEMI, "sum across clients, advisors, securities and dates within one txn_type; "
                         "never across txn_types unsigned"),
        "is_post_departure_txn": (FLAG, "0/1 flag; count flagged rows, never treat as a measure"),
    },
}

DIM_COLUMNS = {
    "dim_advisor": {
        "advisor_id": (KEY, "primary key"),
        "years_experience": ("attribute", "describes the advisor; average or band, never sum"),
        "aum_target_mm": ("attribute", "one target per advisor; summing through a fact repeats it per row"),
    },
    "dim_benchmark": {"benchmark_id": (KEY, "primary key")},
    "dim_client": {
        "client_id": (KEY, "primary key"),
        "age": ("attribute", "describes the client; average or band, never sum"),
        "zip_code": ("attribute", "a code, not a number; load as Text"),
        "initial_aum": ("attribute", "AUM at onboarding, not a current balance; summing through a fact repeats it"),
        "advisor_id": (KEY, "foreign key"),
    },
    "dim_date": {
        "date_id": (KEY, "primary key"),
        "year": (DATE_PART, "group by, never sum"),
        "quarter": (DATE_PART, "group by, never sum"),
        "month": (DATE_PART, "group by, never sum"),
        "week_of_year": (DATE_PART, "group by, never sum"),
        "is_month_end": (FLAG, "filter, never sum"),
        "is_quarter_end": (FLAG, "filter, never sum"),
        "is_year_end": (FLAG, "filter, never sum"),
        "is_trading_day": (FLAG, "filter, never sum"),
    },
    "dim_security": {
        "security_id": (KEY, "primary key"),
        "benchmark_id": (KEY, "foreign key"),
        "expense_ratio_bps": ("attribute", "a rate; average weighted by holdings, never sum"),
    },
}

# Columns that may legitimately be blank (cash transactions have no security, shares or price;
# expense_ratio_bps is blank where the source gives none). Every other classified column must be filled.
ALLOWED_BLANK = {
    ("fact_transactions", "security_id"), ("fact_transactions", "shares"), ("fact_transactions", "price"),
    ("dim_security", "expense_ratio_bps"),
}
CASH_TXN_TYPES = {"Deposit", "Withdrawal", "Advisory Fee"}

# A column counts as numeric if at least this share of its filled values parse,
# so a numeric column with a stray 'n/a' is still caught as unclassified
NUMERIC_SHARE = 0.95

# Tolerances quoted in star_design.md Part C
TOLERANCES = {
    "fee_identity": 0.005 + 1e-9,      # "to within half a cent" (rounding to the cent)
    "trade_identity": 0.005 + 1e-9,
    "alpha_identity": 1e-5,
    "aum_basis_equal": 0.005,
}

# Figures quoted in star_design.md Part C
EXPECTED = {
    "numeric_columns": 47,
    "fee_rows": 122_197,
    "snapshot_months": 60,
    "latest_month": "2024-12-01",
    "firm_aum_latest_bn": 12.73,
    "latest_month_clients": 2_325,
    "aum_sum_all_months_bn": 566.68,
    "aum_months_inflation": 44.5,
    "jan_mean_abs_return_ytd": 0.051,
    "dec_mean_abs_return_ytd": 0.321,
    "january_jump_ratio": 6.4,
    "cash_pct_min": 0.01,
    "cash_pct_max": 0.08,
    "fact_fees_total_mm": 204.68,
    "advisory_fee_txn_total_mm": 263.71,
    "is_return_suspect_rows": 3_875,
    "is_post_departure_txn_rows": 2_410,
}


class MeasureCheckError(Exception):
    """A measure check failed; the Part C classification would be wrong."""


def num(series):
    return pd.to_numeric(series.where(~is_blank(series)), errors="coerce")


def numeric_share(series):
    """Share of filled values that parse as numbers (None if the column is empty)."""
    filled = ~is_blank(series)
    if not filled.any():
        return None
    return float(num(series)[filled].notna().mean())


def main():
    t = load_tables()
    check = Checks(MeasureCheckError)
    found = {}

    # 1. Coverage: every numeric column classified, every classified column fully numeric
    print("1. Coverage")
    rows = []
    for group, spec in [("fact", FACT_COLUMNS), ("dimension", DIM_COLUMNS)]:
        for table, cols in spec.items():
            df = t[table]
            shares = {col: numeric_share(df[col]) for col in df}
            numeric = {col for col, s in shares.items() if s is not None and s >= NUMERIC_SHARE}
            unclassified = sorted(numeric - set(cols))
            partly = sorted(col for col in cols if col in numeric and shares[col] < 1)
            not_numeric = sorted(set(cols) - numeric)
            bad_blanks = sorted(col for col in cols if (table, col) not in ALLOWED_BLANK
                                and is_blank(df[col]).any())
            ok = not (unclassified or partly or not_numeric or bad_blanks)
            print(f"   {table:24} numeric columns {len(numeric):>2}  classified {len(cols):>2}  "
                  f"{'PASS' if ok else 'FAIL'}")
            check(not unclassified, f"{table}: numeric but unclassified {unclassified}")
            check(not partly, f"{table}: classified but has non-numeric values {partly}")
            check(not not_numeric, f"{table}: classified but not numeric {not_numeric}")
            check(not bad_blanks, f"{table}: blanks in columns that must be filled {bad_blanks}")
            for col, (role, rule) in cols.items():
                rows.append({"group": group, "table": table, "column": col, "role": role, "rule": rule})
    check(set(t) == set(FACT_COLUMNS) | set(DIM_COLUMNS), "a table is in neither FACT_COLUMNS nor DIM_COLUMNS")
    found["numeric_columns"] = len(rows)

    # Parse each fact table's numeric columns once
    fees = t["fact_fees"].assign(**{c: num(t["fact_fees"][c]) for c in ["aum_basis", "bps_charged", "amount"]})
    snap_cols = ["aum", "return_ytd", "benchmark_return_ytd", "active_alpha_ytd", "cash_pct", "month"]
    snap = t["fact_portfolio_snapshot"].assign(**{c: num(t["fact_portfolio_snapshot"][c]) for c in snap_cols})
    txn = t["fact_transactions"].assign(**{c: num(t["fact_transactions"][c]) for c in ["shares", "price", "amount"]})
    snap["date"] = parse_iso_date(snap["snapshot_date"])

    # 2. Evidence for each classification
    print("\n2. Evidence")

    # fact_fees: amount is the additive dollar result of a rate applied to a balance
    gap = (fees["amount"] - fees["aum_basis"] * fees["bps_charged"] / 10_000 / 12).abs()
    fee_ok = bool(gap.notna().all() and (gap <= TOLERANCES["fee_identity"]).all())
    found["fee_rows"] = len(fees)
    print(f"   fee amount = aum_basis x bps_charged / 10,000 / 12 on every row: {fee_ok} "
          f"(max gap ${gap.max():.4f})")
    check(fee_ok, "fee amount is not aum_basis x bps / 10,000 / 12 on every row")

    merged = fees.merge(snap, left_on=["client_id", "fee_date"], right_on=["client_id", "snapshot_date"],
                        suffixes=("_fee", "_snap"))
    basis_gap = (merged["aum_basis"] - merged["aum"]).abs()
    basis_ok = bool(len(merged) == len(fees) and basis_gap.notna().all()
                    and (basis_gap <= TOLERANCES["aum_basis_equal"]).all())
    print(f"   fee aum_basis = snapshot aum for the same client-month on all {len(fees):,} fees: {basis_ok}")
    check(basis_ok, "aum_basis is not the snapshot aum, so it may not be a balance")

    # fact_portfolio_snapshot: aum is a balance; summing across months inflates it
    latest = snap["date"].max()
    in_latest = snap["date"].eq(latest)
    firm_latest = snap.loc[in_latest, "aum"].sum()
    all_months = snap["aum"].sum()
    found["snapshot_months"] = snap["date"].nunique()
    found["latest_month"] = latest.strftime("%Y-%m-%d")
    found["firm_aum_latest_bn"] = round(firm_latest / 1e9, 2)
    found["latest_month_clients"] = int(in_latest.sum())
    found["aum_sum_all_months_bn"] = round(all_months / 1e9, 2)
    found["aum_months_inflation"] = round(all_months / firm_latest, 1)
    print(f"   firm AUM, {found['latest_month']} (sum across {in_latest.sum():,} clients): "
          f"${firm_latest / 1e9:,.2f}B")
    print(f"   aum summed across all {found['snapshot_months']} months: ${all_months / 1e9:,.2f}B "
          f"({all_months / firm_latest:.1f}x the latest balance)")

    # Returns: YTD values jump back each January, benchmark repeats on every client, alpha is a difference
    ret = snap["return_ytd"].abs()
    found["jan_mean_abs_return_ytd"] = round(ret[snap["month"].eq(1)].mean(), 3)
    found["dec_mean_abs_return_ytd"] = round(ret[snap["month"].eq(12)].mean(), 3)
    ordered = snap.sort_values(["client_id", "date"])
    change = ordered.groupby("client_id")["return_ytd"].diff().abs()
    consecutive = ordered.groupby("client_id")["date"].diff().dt.days.between(28, 31)
    into_jan = change[consecutive & ordered["month"].eq(1)].mean()
    other = change[consecutive & ordered["month"].ne(1)].mean()
    found["january_jump_ratio"] = round(into_jan / other, 1)
    print(f"   mean |return_ytd|: January {found['jan_mean_abs_return_ytd']:.1%}, "
          f"December {found['dec_mean_abs_return_ytd']:.1%}")
    print(f"   mean month-on-month |change| in return_ytd: into January {into_jan:.1%}, "
          f"other months {other:.1%} ({into_jan / other:.1f}x: the value resets each year)")
    check(into_jan / other > 3, "return_ytd does not jump at January, so it may not be year-to-date")

    bench_per_month = snap.groupby(["benchmark_id", "snapshot_date"])["benchmark_return_ytd"].nunique().max()
    print(f"   benchmark_return_ytd values per benchmark-month: max {bench_per_month}")
    check(bench_per_month == 1, "benchmark_return_ytd differs between clients on the same benchmark-month")

    alpha_gap = (snap["return_ytd"] - snap["benchmark_return_ytd"] - snap["active_alpha_ytd"]).abs()
    alpha_ok = bool(alpha_gap.notna().all() and (alpha_gap <= TOLERANCES["alpha_identity"]).all())
    print(f"   active_alpha_ytd = return_ytd - benchmark_return_ytd on every row: {alpha_ok} "
          f"(max gap {alpha_gap.max():.1e})")
    check(alpha_ok, "active_alpha_ytd is not return_ytd - benchmark_return_ytd on every row")

    cash = snap["cash_pct"]
    found["cash_pct_min"], found["cash_pct_max"] = round(cash.min(), 2), round(cash.max(), 2)
    print(f"   cash_pct range: {cash.min():.2f} to {cash.max():.2f} (a share of AUM)")
    check(cash.notna().all() and cash.between(0, 1).all(), "cash_pct is blank or outside 0 to 1")

    # fact_transactions: direction lives in txn_type; priced rows amount = shares x price
    amt = txn["amount"]
    print(f"   transaction amounts > 0 on every row: {bool((amt > 0).all())} (direction comes from txn_type)")
    check(amt.notna().all() and (amt > 0).all(), "some transaction amounts are blank or signed")
    priced = ~txn["txn_type"].isin(CASH_TXN_TYPES)
    trade_gap = (amt - txn["shares"] * txn["price"]).abs()[priced]
    trade_ok = bool(trade_gap.notna().all() and (trade_gap <= TOLERANCES["trade_identity"]).all())
    print(f"   Buy/Sell/Dividend amount = shares x price on every row: {trade_ok} "
          f"(max gap ${trade_gap.max():.4f})")
    check(trade_ok, "transaction amount is not shares x price on every priced row")

    # Two fee sources: never add together
    found["fact_fees_total_mm"] = round(fees["amount"].sum() / 1e6, 2)
    found["advisory_fee_txn_total_mm"] = round(amt[txn["txn_type"].eq("Advisory Fee")].sum() / 1e6, 2)
    print(f"   fact_fees amount ${found['fact_fees_total_mm']:,.2f}M vs Advisory Fee transactions "
          f"${found['advisory_fee_txn_total_mm']:,.2f}M (separate sources)")

    # Flags: 0/1 only
    for table, col in [("fact_portfolio_snapshot", "is_return_suspect"),
                       ("fact_transactions", "is_post_departure_txn")]:
        values = set(t[table][col])
        found[f"{col}_rows"] = int(t[table][col].eq("1").sum())
        print(f"   {table + '.' + col:46} values {sorted(values)}, flagged rows {found[f'{col}_rows']:,}")
        check(values <= {"0", "1"}, f"{table}.{col} is not a 0/1 flag")

    # 3. Figures quoted in star_design.md
    print("\n3. Figures quoted in star_design.md")
    for name, expected in EXPECTED.items():
        print(f"   {name:30} expected {expected!s:>12}  found {found[name]!s:>12}")
        check(found[name] == expected, f"{name} is {found[name]}, star_design.md quotes {expected}")

    REPORTS_DIR.mkdir(exist_ok=True)
    measures_df = pd.DataFrame(rows)
    measures_df.to_csv(REPORTS_DIR / "measures.csv", index=False)
    check.raise_if_failed()
    counts = measures_df[measures_df["group"] == "fact"]["role"].value_counts().to_dict()
    print(f"\nAll checks passed: {len(measures_df)} numeric columns classified "
          f"(fact columns: {counts}). Wrote {REPORTS_DIR.name}/measures.csv")


if __name__ == "__main__":
    main()
