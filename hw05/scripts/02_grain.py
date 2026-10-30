# 02_grain.py
# HW5 Part B: prove the grain of each Wildcat Capital fact table, i.e. which
# combination of business columns identifies exactly one row.
# Author: Jonah Karst
# Generated: 2026-10-30
#
# For each fact table, the declared grain must be unique and never blank, and
# coarser (and for transactions, the business-column) candidates are tested
# too, so the report shows why the grain is that combination and not another:
#   fact_fees                one client, one month (fee_date, always the 1st)
#   fact_portfolio_snapshot  one client, one month (snapshot_date, always the 1st)
#   fact_transactions        one transaction event; no business-column
#                            combination short of every column is unique, so txn_id
#
# Supporting checks: monthly dates fall on the 1st; attributes that would change
# the grain (advisor, benchmark, account type) are constant per client; snapshot
# series have no missing months; repeated transaction keys are distinct events,
# not duplicate rows (numbers compared as numbers, not text).
#
# Figures quoted in star_design.md Part B are pinned in EXPECTED, so the script
# fails if the data changes under the write-up.
#
# Usage:  python hw05/scripts/02_grain.py
#
# Output (hw05/reports/):
#   grain.csv   one row per candidate grain tested

import pandas as pd

from common import REPORTS_DIR, Checks, is_blank, load_tables, parse_iso_date

FACTS = ["fact_fees", "fact_portfolio_snapshot", "fact_transactions"]

TXN_BUSINESS_COLS = ["client_id", "advisor_id", "security_id", "txn_date", "txn_type",
                     "shares", "price", "amount", "is_post_departure_txn"]
TXN_NUMERIC_COLS = ["shares", "price", "amount"]

# (table, candidate columns, expected unique?, declared grain?)
CANDIDATES = [
    ("fact_fees", ["client_id", "fee_date"], True, True),
    ("fact_fees", ["client_id", "year"], False, False),
    ("fact_fees", ["client_id"], False, False),
    ("fact_portfolio_snapshot", ["client_id", "snapshot_date"], True, True),
    ("fact_portfolio_snapshot", ["client_id", "year"], False, False),
    ("fact_portfolio_snapshot", ["client_id"], False, False),
    ("fact_transactions", ["txn_id"], True, True),
    ("fact_transactions", ["client_id", "txn_date"], False, False),
    ("fact_transactions", ["client_id", "txn_date", "txn_type"], False, False),
    ("fact_transactions", ["client_id", "txn_date", "txn_type", "security_id"], False, False),
    ("fact_transactions", TXN_BUSINESS_COLS, True, False),
]

# Figures quoted in star_design.md Part B
EXPECTED = {
    "fee_rows": 122_197,
    "snapshot_rows": 129_547,
    "clients": 2_500,
    "snapshot_months_without_fee": 7_350,
    "txn_repeated_rows": 1_238,
    "txn_repeated_groups": 616,
    "txn_largest_group": 3,
}


class GrainCheckError(Exception):
    """A grain check failed; the Part B grain sentence would be wrong."""


def normalise_numbers(df, cols):
    """Numbers as numbers, so '67311.3' and '67311.30' count as the same value."""
    out = df.copy()
    for col in cols:
        out[col] = pd.to_numeric(out[col].where(~is_blank(out[col])), errors="raise")
    return out


def main():
    t = load_tables(FACTS)
    t["fact_transactions"] = normalise_numbers(t["fact_transactions"], TXN_NUMERIC_COLS)
    check = Checks(GrainCheckError)
    found = {}

    # Parse each monthly date once; derive year for the coarser candidates
    month_dates = {}
    for table, date_col in [("fact_fees", "fee_date"), ("fact_portfolio_snapshot", "snapshot_date")]:
        dates = parse_iso_date(t[table][date_col])
        month_dates[table] = dates
        if "year" not in t[table]:
            t[table]["year"] = dates.dt.year.astype("Int64").astype(str)

    # 1. Candidate grains: declared grain unique and never blank, alternatives behave as expected
    print("1. Candidate grains")
    rows = []
    for table, cols, expect_unique, declared in CANDIDATES:
        df = t[table]
        dup_rows = int(df.duplicated(cols).sum())
        blank_rows = int(df[cols].astype(str).apply(is_blank).any(axis=1).sum())
        unique = dup_rows == 0
        ok = unique == expect_unique and (not declared or blank_rows == 0)
        label = "all business columns" if cols == TXN_BUSINESS_COLS else " + ".join(cols)
        rows.append({"table": table, "candidate": label, "declared_grain": declared,
                     "rows": len(df), "duplicate_rows": dup_rows, "blank_key_rows": blank_rows,
                     "unique": unique, "expected_unique": expect_unique, "pass": ok})
        tag = "GRAIN" if declared else "     "
        print(f"   {tag} {table:24} {label:48} dup={dup_rows:>7,}  unique={unique}  "
              f"{'PASS' if ok else 'FAIL'}")
        check(ok, f"{table} [{label}] unique={unique}, expected {expect_unique}")

    # 2. Monthly facts: dates on the 1st, attributes constant per client
    print("\n2. Monthly facts")
    for table, date_col in [("fact_fees", "fee_date"), ("fact_portfolio_snapshot", "snapshot_date")]:
        dates = month_dates[table]
        on_first = bool(dates.notna().all() and dates.dt.day.eq(1).all())
        print(f"   {table + '.' + date_col:38} parses and always the 1st of the month: {on_first}")
        check(on_first, f"{table}.{date_col} is not always a valid 1st-of-month date")

    for table, col in [("fact_fees", "advisor_id"), ("fact_portfolio_snapshot", "advisor_id"),
                       ("fact_portfolio_snapshot", "benchmark_id"),
                       ("fact_portfolio_snapshot", "account_type")]:
        per_client = t[table].groupby("client_id")[col].nunique()
        print(f"   {table + '.' + col:38} values per client: max {per_client.max()}")
        check(per_client.max() == 1, f"{table}.{col} varies within a client, so it is part of the grain")

    # Snapshot: every month between a client's first and last snapshot is present
    snap = t["fact_portfolio_snapshot"]
    snap_dates = month_dates["fact_portfolio_snapshot"]
    month_index = snap_dates.dt.year * 12 + snap_dates.dt.month
    g = month_index.groupby(snap["client_id"])
    gaps = int((g.max() - g.min() + 1 != g.nunique()).sum())
    found["snapshot_rows"] = len(snap)
    found["clients"] = snap["client_id"].nunique()
    print(f"   snapshot clients with a missing month between first and last: {gaps} "
          f"of {found['clients']:,}")
    check(gaps == 0, "snapshot series has missing months")

    # Fees: at most one fee per client-month, not every client-month has one
    fees = t["fact_fees"]
    fee_months = set(zip(fees["client_id"], fees["fee_date"]))
    snap_months = set(zip(snap["client_id"], snap["snapshot_date"]))
    found["fee_rows"] = len(fees)
    found["snapshot_months_without_fee"] = len(snap_months - fee_months)
    print(f"   fee client-months with no snapshot: {len(fee_months - snap_months):,}; "
          f"snapshot client-months with no fee: {found['snapshot_months_without_fee']:,}")
    check(not fee_months - snap_months, "a fee falls in a month with no snapshot for that client")

    # fee_type is not part of the grain: client + month is already unique, and the
    # type is not fixed per client (it changes between months), so it is an attribute
    fee_types_per_client = fees.groupby("client_id")["fee_type"].nunique()
    one_type = int((fee_types_per_client == 1).sum())
    print(f"   clients charged only one fee_type across their history: {one_type} "
          f"of {len(fee_types_per_client):,}")
    check(one_type == 0, "some clients have a single fee_type; revisit the fee_type wording in Part B")

    # 3. Transactions: repeated client + date + type + security are separate events
    print("\n3. Transactions")
    txn = t["fact_transactions"]
    key = ["client_id", "txn_date", "txn_type", "security_id"]
    repeated = txn[txn.duplicated(key, keep=False)]
    groups = repeated.groupby(key)
    same_amount = int(repeated.duplicated(key + ["amount"]).sum())
    found["txn_repeated_rows"] = len(repeated)
    found["txn_repeated_groups"] = groups.ngroups
    found["txn_largest_group"] = int(groups.size().max())
    print(f"   rows sharing client + date + type + security: {found['txn_repeated_rows']:,} "
          f"in {found['txn_repeated_groups']:,} groups (largest {found['txn_largest_group']})")
    print(f"   of those, rows that also repeat the amount: {same_amount}")
    print(f"   by txn_type: {repeated['txn_type'].value_counts().to_dict()}")
    check(same_amount == 0, "repeated transaction keys share an amount; check for duplicate rows")

    # 4. Figures quoted in star_design.md
    print("\n4. Figures quoted in star_design.md")
    for name, expected in EXPECTED.items():
        print(f"   {name:30} expected {expected:>9,}  found {found[name]:>9,}")
        check(found[name] == expected, f"{name} is {found[name]:,}, star_design.md quotes {expected:,}")

    REPORTS_DIR.mkdir(exist_ok=True)
    grain_df = pd.DataFrame(rows)
    grain_df.to_csv(REPORTS_DIR / "grain.csv", index=False)
    check.raise_if_failed()
    print(f"\nAll checks passed: {int(grain_df['declared_grain'].sum())} grains proven, "
          f"{len(grain_df)} candidates tested. Wrote {REPORTS_DIR.name}/grain.csv")


if __name__ == "__main__":
    main()
