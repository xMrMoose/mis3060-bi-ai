# 04_relationships.py
# HW5 Part E: check the Power BI model built in Part D against the data, and
# compute every figure the Part E design answers quote.
# Author: Jonah Karst
# Generated: 2026-11-01
#
# MODEL is the intended design: the 13 relationships (many-to-one, single
# direction) with their active flag. The script:
#   0. Agreement     MODEL is exactly the Part A foreign keys, once each, and it
#                    matches the relationships Power BI reports for hw05.pbix
#                    (powerbi/relationships_export.csv, from INFO.VIEW.RELATIONSHIPS),
#                    including active flag, cardinality and cross-filter direction
#   1. Paths         filters flow one side -> many side; the active model has
#                    at most one path between any two tables (Power BI's rule),
#                    and shows which inactive relationship would break that
#   2. Conformed     which dimensions reach which facts through active paths
#   3. (a)-(d)       blank security_id, advisor paths, date join column,
#                    benchmark meaning on snapshots vs transactions
#
# Figures and names quoted in star_design.md Part E are pinned in EXPECTED and
# EXPECTED_NAMES.
#
# Usage:  python hw05/scripts/04_relationships.py
#
# Output (hw05/reports/):
#   relationships.csv   one row per relationship in the model (13)

import importlib.util
from itertools import permutations

import pandas as pd

from common import HW_DIR, REPORTS_DIR, Checks, is_blank, load_tables

KEYS_SCRIPT = HW_DIR / "scripts" / "01_keys.py"
PBI_EXPORT = HW_DIR / "powerbi" / "relationships_export.csv"

FACTS = ["fact_fees", "fact_portfolio_snapshot", "fact_transactions"]

# (many table, column, one table, column, active)
MODEL = [
    ("fact_fees", "fee_date", "dim_date", "date", True),
    ("fact_portfolio_snapshot", "snapshot_date", "dim_date", "date", True),
    ("fact_transactions", "txn_date", "dim_date", "date", True),
    ("fact_fees", "client_id", "dim_client", "client_id", True),
    ("fact_portfolio_snapshot", "client_id", "dim_client", "client_id", True),
    ("fact_transactions", "client_id", "dim_client", "client_id", True),
    ("fact_fees", "advisor_id", "dim_advisor", "advisor_id", True),
    ("fact_portfolio_snapshot", "advisor_id", "dim_advisor", "advisor_id", True),
    ("fact_transactions", "advisor_id", "dim_advisor", "advisor_id", True),
    ("fact_transactions", "security_id", "dim_security", "security_id", True),
    ("fact_portfolio_snapshot", "benchmark_id", "dim_benchmark", "benchmark_id", True),
    ("dim_security", "benchmark_id", "dim_benchmark", "benchmark_id", False),
    ("dim_client", "advisor_id", "dim_advisor", "advisor_id", False),
]

# Which facts each dimension should filter through active relationships
REACHES = {
    "dim_advisor": FACTS,
    "dim_benchmark": ["fact_portfolio_snapshot"],
    "dim_client": FACTS,
    "dim_date": FACTS,
    "dim_security": ["fact_transactions"],
}

ADVISOR_EXAMPLE = "1"
BENCHMARK_EXAMPLES = ["1", "8"]

# Names quoted in star_design.md Part E
EXPECTED_NAMES = {
    "advisor_1": "Danielle Johnson",
    "benchmark_1": "S&P 500",
    "benchmark_8": "Conservative Blend",
    "client_benchmarks": ["60/40 Blend", "Conservative Blend", "S&P 500"],
}

# Figures quoted in star_design.md Part E
EXPECTED = {
    "active_relationships": 11,
    "inactive_relationships": 2,
    "cash_rows": 101_528,
    "cash_share_pct": 34.0,
    "dates_on_date_pct": 100.0,
    "dates_on_date_id_pct": 0.0,
    "date_id_min": 1,
    "date_id_max": 1_827,
    "dim_client_rows": 2_500,
    "fact_rows_advisor_matches_client": 550_316,
    "advisor_1_fees": 5_008,
    "advisor_1_snapshots": 5_304,
    "advisor_1_transactions": 12_661,
    "advisor_1_clients": 107,
    "client_benchmarks_used": 3,
    "security_benchmarks_used": 6,
    "security_txns": 197_044,
    "same_benchmark_pct": 9.4,
    "bm_1_clients": 701,
    "bm_1_snapshots": 36_528,
    "bm_1_securities": 101,
    "bm_1_security_txns": 39_440,
    "bm_1_trading_clients": 2_376,
    "bm_1_trading_clients_with_bm_1": 666,
    "bm_1_trades_by_other_clients_pct": 71.5,
    "bm_8_clients": 967,
    "bm_8_snapshots": 50_117,
    "bm_8_securities": 0,
    "bm_8_security_txns": 0,
    "bm_8_client_txns": 115_882,
}


class RelationshipCheckError(Exception):
    """A model check failed; the Part E answers would be wrong."""


def load_part_a_keys():
    spec = importlib.util.spec_from_file_location("keys", KEYS_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.FOREIGN_KEYS


def read_pbi_export(path):
    """Relationships as Power BI reports them (DAX query view: EVALUATE INFO.VIEW.RELATIONSHIPS()).

    Returns (set of (many table, column, one table, column, active, cardinality, cross filter),
    number of hidden Auto date/time relationships skipped), or (None, 0) if the export is missing.
    Column headers may come with or without [brackets].
    """
    if not path.exists():
        return None, 0
    # Pasted from DAX query view the file is tab-separated; saved from Excel it is comma-separated
    df = pd.read_csv(path, dtype=str, keep_default_na=False, sep=None, engine="python")
    df.columns = [c.strip().strip("[]").lower() for c in df.columns]
    # Auto date/time adds a hidden LocalDateTable_<guid> per date column; not part of the design
    auto = df["totable"].str.startswith(("LocalDateTable_", "DateTableTemplate_"))
    df = df[~auto]
    # Power BI names are case-insensitive, and INFO.VIEW.RELATIONSHIPS reports dim_date's column as
    # [Date] though the relationship text says [date], so names are compared in lower case
    rels = set()
    for _, r in df.iterrows():
        cross = r["crossfilteringbehavior"].strip().lower()
        rels.add((r["fromtable"].strip().lower(), r["fromcolumn"].strip().lower(),
                  r["totable"].strip().lower(), r["tocolumn"].strip().lower(),
                  r["isactive"].strip().lower() == "true",
                  f"{r['fromcardinality'].strip().lower()}-to-{r['tocardinality'].strip().lower()}",
                  "onedirection" if cross in ("onedirection", "single") else cross))
    return rels, int(auto.sum())


def filter_paths(relationships, source, target):
    """All filter paths from source to target. A filter flows from the one side to the many side."""
    edges = {}
    for many, _, one, _ in relationships:
        edges.setdefault(one, []).append(many)
    paths, stack = [], [[source]]
    while stack:
        path = stack.pop()
        for nxt in edges.get(path[-1], []):
            if nxt in path:
                continue
            if nxt == target:
                paths.append(path + [nxt])
            else:
                stack.append(path + [nxt])
    return paths


def ambiguous_pairs(relationships):
    tables = {r[0] for r in relationships} | {r[2] for r in relationships}
    return {(a, b): p for a, b in permutations(sorted(tables), 2)
            if len(p := filter_paths(relationships, a, b)) > 1}


def main():
    t = load_tables()
    check = Checks(RelationshipCheckError)
    found, names = {}, {}

    # 0. MODEL is the Part A foreign keys, once each, and matches what Power BI reports
    print("0. Agreement")
    model_keys = [r[:4] for r in MODEL]
    check(len(model_keys) == len(set(model_keys)), "MODEL lists a relationship more than once")
    check(set(model_keys) == set(load_part_a_keys()), "MODEL differs from the Part A foreign keys")
    exported, auto_date = read_pbi_export(PBI_EXPORT)
    if exported is None:
        print(f"   {PBI_EXPORT.name} not found")
        check(False, f"export the model's relationships to powerbi/{PBI_EXPORT.name} (see README)")
    else:
        expected = {tuple(x.lower() for x in r[:4]) + (r[4], "many-to-one", "onedirection") for r in MODEL}
        missing, extra = sorted(expected - exported), sorted(exported - expected)
        if auto_date:
            print(f"   skipped {auto_date} hidden Auto date/time relationships (LocalDateTable_*)")
        print(f"   hw05.pbix reports {len(exported)} relationships; matching MODEL "
              f"(active flag, many-to-one, single direction): {not missing and not extra}")
        for r in missing:
            print(f"   in MODEL, not in hw05.pbix: {r}")
        for r in extra:
            print(f"   in hw05.pbix, not in MODEL: {r}")
        check(not missing and not extra, "hw05.pbix relationships differ from MODEL")

    # 1. Paths
    print("\n1. Filter paths")
    active = [r[:4] for r in MODEL if r[4]]
    found["active_relationships"] = len(active)
    found["inactive_relationships"] = len(MODEL) - len(active)
    ambiguous = ambiguous_pairs(active)
    print(f"   model: {len(active)} active, {len(MODEL) - len(active)} inactive; "
          f"pairs with more than one active path: {len(ambiguous)}")
    check(not ambiguous, f"active model has ambiguous paths: {sorted(ambiguous)}")

    rows = []
    for many, mcol, one, ocol, is_active in MODEL:
        note = ""
        if not is_active:
            with_it = ambiguous_pairs(active + [(many, mcol, one, ocol)])
            note = ("would create a second path: " + "; ".join(f"{a} -> {b}" for a, b in sorted(with_it))
                    if with_it else "allowed active (no second path); inactive by design choice")
            print(f"   if {many}.{mcol} -> {one} were active: {note}")
        rows.append({"from": f"{many}[{mcol}]", "to": f"{one}[{ocol}]", "cardinality": "many-to-one",
                     "cross_filter": "single", "active": is_active, "note": note})
    advisor_extra = ambiguous_pairs(active + [("dim_client", "advisor_id", "dim_advisor", "advisor_id")])
    check(set(advisor_extra) == {("dim_advisor", f) for f in FACTS},
          "dim_client -> dim_advisor should be the second path from dim_advisor to each fact")
    check(not ambiguous_pairs(active + [("dim_security", "benchmark_id", "dim_benchmark", "benchmark_id")]),
          "dim_security -> dim_benchmark should be allowed active (no second path)")

    # 2. Conformed dimensions
    print("\n2. Dimensions reaching each fact through active relationships")
    for dim, expected_facts in REACHES.items():
        reached = [f for f in FACTS if filter_paths(active, dim, f)]
        print(f"   {dim:14} -> {', '.join(reached)}")
        check(reached == expected_facts, f"{dim} reaches {reached}, expected {expected_facts}")

    fees, snap, txn = t["fact_fees"], t["fact_portfolio_snapshot"], t["fact_transactions"]
    dim_date, dim_client = t["dim_date"], t["dim_client"]
    client_adv = dim_client.set_index("client_id")["advisor_id"]
    bm_names = t["dim_benchmark"].set_index("benchmark_id")["name"]

    print("\n3. Design questions")

    # (a) Blank security_id = cash transactions
    blank_sec = is_blank(txn["security_id"])
    found["cash_rows"] = int(blank_sec.sum())
    found["cash_share_pct"] = round(100 * blank_sec.mean(), 1)
    print(f"   (a) blank security_id: {found['cash_rows']:,} rows ({found['cash_share_pct']}%), "
          f"types {sorted(txn.loc[blank_sec, 'txn_type'].unique())}")

    # (b) Advisor: fact advisor = client advisor on every row, so both paths give the same numbers
    matches = sum(int(df["advisor_id"].eq(df["client_id"].map(client_adv)).sum()) for df in (fees, snap, txn))
    total = sum(len(df) for df in (fees, snap, txn))
    found["fact_rows_advisor_matches_client"] = matches
    found["dim_client_rows"] = len(dim_client)
    print(f"   (b) fact advisor_id = client's advisor_id on {matches:,} of {total:,} fact rows "
          "(so rows per advisor are identical through either path)")
    check(matches == total, "a fact row's advisor differs from the client's advisor")
    adv = t["dim_advisor"].set_index("advisor_id").loc[ADVISOR_EXAMPLE]
    names["advisor_1"] = f"{adv['first_name']} {adv['last_name']}"
    found["advisor_1_fees"] = int(fees["advisor_id"].eq(ADVISOR_EXAMPLE).sum())
    found["advisor_1_snapshots"] = int(snap["advisor_id"].eq(ADVISOR_EXAMPLE).sum())
    found["advisor_1_transactions"] = int(txn["advisor_id"].eq(ADVISOR_EXAMPLE).sum())
    found["advisor_1_clients"] = int(client_adv.eq(ADVISOR_EXAMPLE).sum())
    print(f"       advisor {ADVISOR_EXAMPLE} ({names['advisor_1']}): fees {found['advisor_1_fees']:,}, "
          f"snapshots {found['advisor_1_snapshots']:,}, transactions {found['advisor_1_transactions']:,}; "
          f"clients {found['advisor_1_clients']} of {found['dim_client_rows']:,} in dim_client")

    # (c) Fact dates match dim_date[date], never date_id
    fact_dates = pd.concat([fees["fee_date"], snap["snapshot_date"], txn["txn_date"]])
    found["dates_on_date_pct"] = round(100 * fact_dates.isin(dim_date["date"]).mean(), 1)
    found["dates_on_date_id_pct"] = round(100 * fact_dates.isin(dim_date["date_id"]).mean(), 1)
    date_ids = pd.to_numeric(dim_date["date_id"])
    found["date_id_min"], found["date_id_max"] = int(date_ids.min()), int(date_ids.max())
    print(f"   (c) fact dates match dim_date[date] {found['dates_on_date_pct']}%, "
          f"dim_date[date_id] {found['dates_on_date_id_pct']}% "
          f"(date_id runs {found['date_id_min']} to {found['date_id_max']:,})")

    # (d) Benchmark means two different things on snapshots and transactions
    bm_per_client = snap.groupby("client_id")["benchmark_id"].nunique()
    check(bm_per_client.max() == 1, "a client has more than one portfolio benchmark")
    client_bm = snap.drop_duplicates("client_id").set_index("client_id")["benchmark_id"]
    sec_bm = t["dim_security"].set_index("security_id")["benchmark_id"]
    trades = txn[~blank_sec]
    trade_bm = trades["security_id"].map(sec_bm)
    trade_client_bm = trades["client_id"].map(client_bm)
    txn_client_bm = txn["client_id"].map(client_bm)
    names["client_benchmarks"] = sorted(bm_names[client_bm.unique()])
    found["client_benchmarks_used"] = client_bm.nunique()
    found["security_benchmarks_used"] = sec_bm.nunique()
    found["security_txns"] = len(trades)
    found["same_benchmark_pct"] = round(100 * trade_bm.eq(trade_client_bm).mean(), 1)
    print(f"   (d) benchmarks used by client portfolios: {found['client_benchmarks_used']} "
          f"{names['client_benchmarks']}; by securities: {found['security_benchmarks_used']}")
    print(f"       security trades whose security benchmark = client's portfolio benchmark: "
          f"{found['same_benchmark_pct']}% of {found['security_txns']:,}")
    for bm in BENCHMARK_EXAMPLES:
        names[f"benchmark_{bm}"] = bm_names[bm]
        in_bm = trade_bm.eq(bm)
        found[f"bm_{bm}_clients"] = int(client_bm.eq(bm).sum())
        found[f"bm_{bm}_snapshots"] = int(snap["benchmark_id"].eq(bm).sum())
        found[f"bm_{bm}_securities"] = int(sec_bm.eq(bm).sum())
        found[f"bm_{bm}_security_txns"] = int(in_bm.sum())
        found[f"bm_{bm}_client_txns"] = int(txn_client_bm.eq(bm).sum())
        print(f"       {names[f'benchmark_{bm}']:18} snapshots {found[f'bm_{bm}_snapshots']:>7,} "
              f"({found[f'bm_{bm}_clients']:,} clients); trades in its {found[f'bm_{bm}_securities']} "
              f"securities {found[f'bm_{bm}_security_txns']:>7,}; transactions by its clients "
              f"{found[f'bm_{bm}_client_txns']:>7,}")
    sp_trades = trades[trade_bm.eq("1")]
    sp_traders = set(sp_trades["client_id"])
    sp_clients = set(client_bm.index[client_bm.eq("1")])
    found["bm_1_trading_clients"] = len(sp_traders)
    found["bm_1_trading_clients_with_bm_1"] = len(sp_traders & sp_clients)
    found["bm_1_trades_by_other_clients_pct"] = round(100 * (~sp_trades["client_id"].isin(sp_clients)).mean(), 1)
    print(f"       clients trading S&P 500-benchmarked securities: {found['bm_1_trading_clients']:,}, "
          f"of whom {found['bm_1_trading_clients_with_bm_1']:,} have an S&P 500 portfolio; "
          f"{found['bm_1_trades_by_other_clients_pct']}% of those trades are by other clients")

    # 4. Figures and names quoted in star_design.md
    print("\n4. Figures and names quoted in star_design.md")
    for name, expected in {**EXPECTED, **EXPECTED_NAMES}.items():
        actual = found.get(name, names.get(name))
        print(f"   {name:34} expected {expected!s:>9}  found {actual!s:>9}")
        check(actual == expected, f"{name} is {actual}, star_design.md quotes {expected}")

    REPORTS_DIR.mkdir(exist_ok=True)
    pd.DataFrame(rows).to_csv(REPORTS_DIR / "relationships.csv", index=False)
    check.raise_if_failed()
    print(f"\nAll checks passed: {len(MODEL)} relationships ({found['active_relationships']} active) "
          f"match hw05.pbix, no ambiguous paths. Wrote {REPORTS_DIR.name}/relationships.csv")


if __name__ == "__main__":
    main()
