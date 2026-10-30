# 01_keys.py
# HW5 Part A: prove every primary key and foreign key in the Wildcat Capital
# Clean tables before they are modeled as a star schema in Power BI.
# Author: Jonah Karst
# Generated: 2026-10-30
#
# Checks, all on data/clean (files read as text, dtype=str, keep_default_na=False):
#   0. Agreement         the key lists below match the ones HW4 validated
#   1. Primary keys      non-blank, unique, canonical whole numbers (Power BI Whole Number)
#   2. Foreign keys      every non-blank FK value exists in its target column,
#                        using check_referential_integrity() from HW4
#   3. Blank keys        fact_transactions.security_id is blank exactly on the
#                        cash txn_types (Deposit, Withdrawal, Advisory Fee)
#   4. Date join column  fact dates match dim_date[date], not dim_date[date_id]
#   5. Look-alike links  columns that resemble keys but are not FKs
#
# Every check runs; both reports are written together at the end, then the
# script raises KeyCheckError if any check failed.
#
# Usage:  python hw05/scripts/01_keys.py
#
# Outputs (hw05/reports/):
#   keys_pk.csv   one row per table (8)
#   keys_fk.csv   one row per relationship (13)

import importlib.util

import pandas as pd

from common import (HW_DIR, REPORTS_DIR, Checks, is_blank, is_iso_date, is_whole_number,
                    load_tables, parse_iso_date)

HW04_VALIDATE = HW_DIR.parent / "hw04" / "scripts" / "03_validate.py"

PRIMARY_KEYS = {
    "dim_advisor": "advisor_id",
    "dim_benchmark": "benchmark_id",
    "dim_client": "client_id",
    "dim_date": "date_id",
    "dim_security": "security_id",
    "fact_fees": "fee_id",
    "fact_portfolio_snapshot": "snapshot_id",
    "fact_transactions": "txn_id",
}

# (table, column, target table, target column)
FOREIGN_KEYS = [
    ("dim_client", "advisor_id", "dim_advisor", "advisor_id"),
    ("dim_security", "benchmark_id", "dim_benchmark", "benchmark_id"),
    ("fact_fees", "client_id", "dim_client", "client_id"),
    ("fact_fees", "advisor_id", "dim_advisor", "advisor_id"),
    ("fact_fees", "fee_date", "dim_date", "date"),
    ("fact_portfolio_snapshot", "client_id", "dim_client", "client_id"),
    ("fact_portfolio_snapshot", "advisor_id", "dim_advisor", "advisor_id"),
    ("fact_portfolio_snapshot", "benchmark_id", "dim_benchmark", "benchmark_id"),
    ("fact_portfolio_snapshot", "snapshot_date", "dim_date", "date"),
    ("fact_transactions", "client_id", "dim_client", "client_id"),
    ("fact_transactions", "advisor_id", "dim_advisor", "advisor_id"),
    ("fact_transactions", "security_id", "dim_security", "security_id"),
    ("fact_transactions", "txn_date", "dim_date", "date"),
]

CASH_TXN_TYPES = {"Deposit", "Withdrawal", "Advisory Fee"}
SECURITY_TXN_TYPES = {"Buy", "Sell", "Dividend"}


class KeyCheckError(Exception):
    """A key check failed; the Part A table would be wrong."""


def load_hw04():
    """Import the HW4 validation script for its RI function and key lists."""
    if not HW04_VALIDATE.exists():
        raise KeyCheckError(f"{HW04_VALIDATE} not found: 01_keys.py reuses "
                            "check_referential_integrity() from HW4")
    spec = importlib.util.spec_from_file_location("hw04_validate", HW04_VALIDATE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    hw04 = load_hw04()
    check_referential_integrity = hw04.check_referential_integrity
    t = load_tables()
    check = Checks(KeyCheckError)

    # 0. This design must agree with the keys HW4 validated
    check(PRIMARY_KEYS == hw04.PKS, "PRIMARY_KEYS differs from HW4 PKS")
    check(set(FOREIGN_KEYS) == set(hw04.RELATIONSHIPS), "FOREIGN_KEYS differs from HW4 RELATIONSHIPS")

    # 1. Primary keys
    print("1. Primary keys")
    pk_rows = []
    for name, pk in PRIMARY_KEYS.items():
        col = t[name][pk]
        row = {
            "table": name,
            "type": "Fact" if name.startswith("fact_") else "Dimension",
            "primary_key": pk,
            "rows": len(col),
            "blank": int(is_blank(col).sum()),
            "duplicates": int(col.duplicated().sum()),
            "whole_number": is_whole_number(col),
        }
        row["pass"] = row["blank"] == 0 and row["duplicates"] == 0 and row["whole_number"]
        pk_rows.append(row)
        print(f"   {name:25} {pk:13} rows={row['rows']:>7,}  blank={row['blank']}  "
              f"dup={row['duplicates']}  whole={row['whole_number']}  {'PASS' if row['pass'] else 'FAIL'}")
    pk_df = pd.DataFrame(pk_rows)
    check(pk_df["pass"].all(), "a primary key is blank, duplicated or not a whole number")

    # dim_date[date] is the join target for the facts, so it must also be unique
    dates = t["dim_date"]["date"]
    date_target_ok = not dates.duplicated().any() and not is_blank(dates).any() and is_iso_date(dates)
    print(f"   dim_date[date] (date join target): unique, non-blank, valid dates  "
          f"{'PASS' if date_target_ok else 'FAIL'}")
    check(date_target_ok, "dim_date[date] is not unique valid dates, so it cannot be the one side")

    # 2. Foreign keys
    print("\n2. Foreign keys")
    fk_rows = []
    for table, col, target, target_col in FOREIGN_KEYS:
        ri = check_referential_integrity(t[table], col, t[target], target_col)
        values = t[table][col]
        non_blank = values[~is_blank(values)]
        if target_col == "date":
            key_type = "Date" if is_iso_date(non_blank) else "INVALID DATE"
        else:
            key_type = "Whole Number" if is_whole_number(non_blank) else "NOT WHOLE NUMBER"
        row = {
            "table": table, "foreign_key": col, "target": f"{target}[{target_col}]",
            "rows": ri["rows"], "blank_rows": ri["null_key_rows"],
            "matched_rows": ri["matched_rows"], "orphan_rows": ri["orphan_row_count"],
            "match_rate": round(ri["match_rate"], 6), "key_type": key_type,
        }
        row["pass"] = row["orphan_rows"] == 0 and key_type in ("Date", "Whole Number")
        fk_rows.append(row)
        print(f"   {table + '.' + col:38} -> {row['target']:28} blank={row['blank_rows']:>7,}  "
              f"orphans={row['orphan_rows']}  match={row['match_rate']:.2%}  {'PASS' if row['pass'] else 'FAIL'}")
    fk_df = pd.DataFrame(fk_rows)
    check(fk_df["pass"].all(), "a foreign key has orphans or values of the wrong type")
    blank_fks = fk_df[fk_df["blank_rows"] > 0]
    check(list(zip(blank_fks["table"], blank_fks["foreign_key"])) == [("fact_transactions", "security_id")],
          "a foreign key other than fact_transactions.security_id has blanks")

    # 3. Blank security_id only on cash transactions
    print("\n3. Blank keys")
    txn = t["fact_transactions"]
    unknown = set(txn["txn_type"]) - CASH_TXN_TYPES - SECURITY_TXN_TYPES
    check(not unknown, f"unexpected txn_type values: {sorted(unknown)}")
    blank_sec = is_blank(txn["security_id"])
    is_cash = txn["txn_type"].isin(CASH_TXN_TYPES)
    by_type = blank_sec.groupby(txn["txn_type"]).agg(["sum", "size"])
    for txn_type, (n_blank, total) in by_type.iterrows():
        print(f"   {txn_type:13} {n_blank:>7,} of {total:>7,} blank security_id")
    check((blank_sec == is_cash).all(),
          "security_id is blank on a security transaction, or filled on a cash transaction")
    print(f"   security_id blank on exactly the {int(is_cash.sum()):,} cash rows "
          f"({', '.join(sorted(CASH_TXN_TYPES))})")

    # 4. Which dim_date column the fact dates match
    print("\n4. Date join column")
    for table, col in [("fact_fees", "fee_date"), ("fact_portfolio_snapshot", "snapshot_date"),
                       ("fact_transactions", "txn_date")]:
        values = t[table][col]
        on_date = values.isin(t["dim_date"]["date"]).mean()
        on_date_id = values.isin(t["dim_date"]["date_id"]).mean()
        print(f"   {table + '.' + col:38} matches dim_date[date] {on_date:.2%}, "
              f"dim_date[date_id] {on_date_id:.2%}  ({values.min()} to {values.max()})")
        check(on_date == 1 and on_date_id == 0, f"{table}.{col} does not join on dim_date[date]")

    # 5. Columns that look like keys but are not foreign keys
    print("\n5. Look-alike links (not foreign keys)")
    proxy = t["dim_benchmark"]["ticker_proxy"]
    proxy_hits = int(proxy.isin(t["dim_security"]["ticker"]).sum())
    print(f"   dim_benchmark.ticker_proxy in dim_security[ticker]: {proxy_hits} of {len(proxy)}")
    check(proxy_hits == 0, "ticker_proxy matches dim_security tickers; reconsider it as a FK")
    snap = t["fact_portfolio_snapshot"]
    snap_dates = parse_iso_date(snap["snapshot_date"])
    parts_ok = (pd.to_numeric(snap["year"], errors="coerce").eq(snap_dates.dt.year).all()
                and pd.to_numeric(snap["month"], errors="coerce").eq(snap_dates.dt.month).all())
    print(f"   fact_portfolio_snapshot.year/month are parts of snapshot_date: {parts_ok}")
    check(parts_ok, "snapshot year/month disagree with snapshot_date")

    # Write both reports together, after every check, so they always describe the same run
    REPORTS_DIR.mkdir(exist_ok=True)
    pk_df.to_csv(REPORTS_DIR / "keys_pk.csv", index=False)
    fk_df.to_csv(REPORTS_DIR / "keys_fk.csv", index=False)
    check.raise_if_failed()
    print(f"\nAll checks passed: {len(pk_df)} primary keys, {len(fk_df)} foreign keys. "
          f"Wrote {REPORTS_DIR.name}/keys_pk.csv and {REPORTS_DIR.name}/keys_fk.csv")


if __name__ == "__main__":
    main()
