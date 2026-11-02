# 05_questions.py
# HW5 Part F: answer three manager questions (one per fact table) two ways:
# what a single Power BI visual with default Sum would show, and the correct
# answer. Where the two differ, the model needs DAX or a schema change.
# Author: Jonah Karst
# Generated: 2026-11-01
#
#   Q1 fact_fees                fee revenue by advisor and year       (single visual is correct)
#   Q2 fact_portfolio_snapshot  AUM at each year end                  (default Sum adds 12 balances)
#   Q3 fact_transactions        net new money (deposits - withdrawals) (default Sum adds both)
#
# Figures quoted in star_design.md Part F are pinned in EXPECTED.
#
# Usage:  python hw05/scripts/05_questions.py

import pandas as pd

from common import Checks, load_tables, parse_iso_date

LAST_MONTH = pd.Timestamp("2024-12-01")   # "before December 2024" in Part F

# Figures quoted in star_design.md Part F
EXPECTED = {
    "q1_fees_2024_mm": 48.71,
    "q1_top_advisor_2024": "Jeffery Wagner",
    "q1_top_advisor_2024_fees_mm": 3.18,
    "q1_fee_advisor_is_client_advisor": True,
    "q2_2024_single_visual_bn": 135.46,
    "q2_2024_year_end_bn": 12.73,
    "q2_2024_inflation": 10.6,
    "q2_min_inflation": 10.6,
    "q2_max_inflation": 12.4,
    "q2_2024_advisors": 25,
    "q2_2024_advisor_min_inflation": 10.6,
    "q2_2024_advisor_max_inflation": 10.7,
    "q2_snapshots_on_month_end_flag": 0,
    "q2_snapshots_on_year_end_flag": 0,
    "q2_clients_ending_before_last_month": 175,
    "q3_deposits_bn": 1.82,
    "q3_withdrawals_bn": 1.49,
    "q3_single_visual_bn": 3.31,
    "q3_net_new_money_mm": 327.44,
    "q3_months": 60,
    "q3_months_with_net_outflow": 0,
}


class QuestionCheckError(Exception):
    """A Part F figure changed; the reflection would quote a wrong number."""


def main():
    t = load_tables(["dim_advisor", "dim_client", "dim_date", "fact_fees",
                     "fact_portfolio_snapshot", "fact_transactions"])
    check = Checks(QuestionCheckError)
    found = {}
    client_adv = t["dim_client"].set_index("client_id")["advisor_id"]

    # Q1 fees: fully additive, conformed dimensions -> one matrix (advisor x year, Sum of amount)
    fees = t["fact_fees"].assign(amount=lambda d: pd.to_numeric(d["amount"]),
                                 year=lambda d: parse_iso_date(d["fee_date"]).dt.year)
    fees_2024 = fees[fees["year"].eq(2024)].groupby("advisor_id")["amount"].sum()
    top = fees_2024.idxmax()
    adv = t["dim_advisor"].set_index("advisor_id").loc[top]
    found["q1_fees_2024_mm"] = round(fees_2024.sum() / 1e6, 2)
    found["q1_top_advisor_2024"] = f"{adv['first_name']} {adv['last_name']}"
    found["q1_top_advisor_2024_fees_mm"] = round(fees_2024[top] / 1e6, 2)
    # Row by row, so the result is the same through the inactive dim_client -> dim_advisor path
    found["q1_fee_advisor_is_client_advisor"] = bool(fees["advisor_id"].eq(fees["client_id"].map(client_adv)).all())
    print("Q1 fee revenue by advisor and year (single visual: Sum of amount)")
    print(f"   2024 total ${found['q1_fees_2024_mm']}M; top advisor {top} ({found['q1_top_advisor_2024']}) "
          f"${found['q1_top_advisor_2024_fees_mm']}M")

    # Q2 AUM at year end: a balance; a year column sums its 12 monthly snapshots
    snap = t["fact_portfolio_snapshot"].assign(aum=lambda d: pd.to_numeric(d["aum"]),
                                               date=lambda d: parse_iso_date(d["snapshot_date"]))
    snap["year"] = snap["date"].dt.year
    december = snap["date"].dt.month.eq(12)
    single = snap.groupby("year")["aum"].sum()
    year_end = snap[december].groupby("year")["aum"].sum()
    ratio = (single / year_end).round(1)
    found["q2_2024_single_visual_bn"] = round(single[2024] / 1e9, 2)
    found["q2_2024_year_end_bn"] = round(year_end[2024] / 1e9, 2)
    found["q2_2024_inflation"] = ratio[2024]
    found["q2_min_inflation"], found["q2_max_inflation"] = ratio.min(), ratio.max()
    in_2024 = snap["year"].eq(2024)
    adv_ratio = (snap[in_2024].groupby("advisor_id")["aum"].sum()
                 / snap[in_2024 & december].groupby("advisor_id")["aum"].sum()).round(1)
    found["q2_2024_advisors"] = len(adv_ratio)
    found["q2_2024_advisor_min_inflation"] = adv_ratio.min()
    found["q2_2024_advisor_max_inflation"] = adv_ratio.max()

    dim_date = t["dim_date"]
    for col in ["is_month_end", "is_year_end"]:
        values = set(dim_date[col])
        check(values == {"0", "1"}, f"dim_date.{col} is not a 0/1 flag with both values present: {sorted(values)}")
    flags = snap.merge(dim_date[["date", "is_month_end", "is_year_end"]], how="left",
                       left_on="snapshot_date", right_on="date", suffixes=("", "_dim"), validate="many_to_one")
    check(flags["is_month_end"].notna().all(), "some snapshot dates are missing from dim_date")
    found["q2_snapshots_on_month_end_flag"] = int(flags["is_month_end"].eq("1").sum())
    found["q2_snapshots_on_year_end_flag"] = int(flags["is_year_end"].eq("1").sum())
    check(snap["date"].max() == LAST_MONTH, f"data no longer ends {LAST_MONTH:%Y-%m-%d}; update Part F wording")
    last = snap.groupby("client_id")["date"].max()
    found["q2_clients_ending_before_last_month"] = int((last < LAST_MONTH).sum())
    print("\nQ2 AUM at year end (single visual sums 12 monthly balances per year)")
    for year in single.index:
        print(f"   {year}: single visual ${single[year] / 1e9:,.2f}B, December snapshot "
              f"${year_end[year] / 1e9:,.2f}B ({ratio[year]}x)")
    print(f"   2024 by advisor: {found['q2_2024_advisors']} advisors, "
          f"{found['q2_2024_advisor_min_inflation']}x to {found['q2_2024_advisor_max_inflation']}x")
    print(f"   snapshots on a dim_date is_month_end day: {found['q2_snapshots_on_month_end_flag']}, "
          f"is_year_end day: {found['q2_snapshots_on_year_end_flag']} (all dated the 1st)")
    print(f"   clients whose last snapshot is before {LAST_MONTH:%Y-%m}: "
          f"{found['q2_clients_ending_before_last_month']}")

    # Q3 net new money: amounts are unsigned, direction is in txn_type; months are year-months
    txn = t["fact_transactions"].assign(amount=lambda d: pd.to_numeric(d["amount"]),
                                        month=lambda d: parse_iso_date(d["txn_date"]).dt.to_period("M"))
    flows = txn[txn["txn_type"].isin(["Deposit", "Withdrawal"])]
    monthly = (flows.pivot_table(index="month", columns="txn_type", values="amount", aggfunc="sum")
               .reindex(columns=["Deposit", "Withdrawal"]).fillna(0))
    dep, wd = monthly["Deposit"].sum(), monthly["Withdrawal"].sum()
    found["q3_deposits_bn"] = round(dep / 1e9, 2)
    found["q3_withdrawals_bn"] = round(wd / 1e9, 2)
    found["q3_single_visual_bn"] = round((dep + wd) / 1e9, 2)
    found["q3_net_new_money_mm"] = round((dep - wd) / 1e6, 2)
    found["q3_months"] = len(monthly)
    found["q3_months_with_net_outflow"] = int((monthly["Deposit"] < monthly["Withdrawal"]).sum())
    print("\nQ3 net new money (single visual adds deposits and withdrawals)")
    print(f"   deposits ${found['q3_deposits_bn']}B, withdrawals ${found['q3_withdrawals_bn']}B; "
          f"single visual ${found['q3_single_visual_bn']}B; net new money ${found['q3_net_new_money_mm']}M; "
          f"months with net outflow {found['q3_months_with_net_outflow']} of {found['q3_months']}")

    print("\nFigures quoted in star_design.md")
    for name, expected in EXPECTED.items():
        print(f"   {name:38} expected {expected!s:>14}  found {found[name]!s:>14}")
        check(found[name] == expected, f"{name} is {found[name]}, star_design.md quotes {expected}")
    check.raise_if_failed()
    print(f"\nAll checks passed: {len(EXPECTED)} Part F figures verified.")


if __name__ == "__main__":
    main()
