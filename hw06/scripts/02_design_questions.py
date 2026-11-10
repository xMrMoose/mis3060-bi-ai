# 02_design_questions.py
# HW6 Part C: the pandas evidence behind the four design questions in powerbi/measures.md.
# Every figure Part C quotes is computed here and pinned in EXPECTED. The script fails if a
# figure changes or if it computes a figure that is not pinned, so the written answers can't
# drift from the data. Figures quoted from the Part A/B measures (e.g., Fee Yield by tier) are
# reconciled in reports/measure_reconciliation.csv instead.
# Writes reports/design_questions.csv (question, figure, value) only when every figure is confirmed.
# Author: Jonah Karst
# Generated: 2026-11-09
#
# Run from the repo root:  python hw06/scripts/02_design_questions.py
# Exit codes: 0 all figures confirmed, 1 a figure changed, 2 bad input.

import sys
from pathlib import Path

import pandas as pd

HW_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = HW_DIR / "data" / "clean"
OUTPUT = HW_DIR / "reports" / "design_questions.csv"

# (question, figure) -> (value quoted in Part C, tolerance)
EXPECTED = {
    # (a) Ending AUM vs SUMX over clients
    ("a", "ending_aum"): (12_729_572_078.86, 0.01),
    ("a", "sumx_client_ending_aum"): (13_149_297_713.80, 0.01),
    ("a", "difference"): (419_725_634.94, 0.01),
    ("a", "difference_pct_of_ending_aum"): (0.0330, 0.0001),
    ("a", "ending_clients"): (2_325, 0),
    ("a", "departed_clients"): (175, 0),
    ("a", "departed_clients_last_balance"): (419_725_634.94, 0.01),
    ("a", "difference_equals_departed_balance"): (1, 0),
    ("a", "departed_in_2022"): (13, 0),
    ("a", "departed_in_2023"): (162, 0),
    ("a", "departed_flagged_inactive"): (175, 0),
    # (b) Fee Yield vs Effective Fee Rate, 2024
    ("b", "fee_yield_bps_2024"): (43.1543, 0.0001),
    ("b", "effective_fee_rate_bps_2024"): (45.5323, 0.0001),
    ("b", "gap_bps_2024"): (2.3780, 0.0001),
    ("b", "snapshot_months_2024"): (27_900, 0),
    ("b", "billed_months_2024"): (26_216, 0),
    ("b", "snapshot_months_without_fee_2024"): (1_684, 0),
    ("b", "months_share_without_fee_2024"): (0.0604, 0.0001),
    ("b", "aum_share_without_fee_2024"): (0.0522, 0.0001),
    ("b", "billed_months_aum_basis_equals_aum"): (1.0, 0),
    ("b", "fee_yield_bps_2024_billed_months_only"): (45.5323, 0.0001),
    ("b", "snapshot_months_all_years"): (129_547, 0),
    ("b", "snapshot_months_without_fee_all_years"): (7_350, 0),
    ("b", "months_share_without_fee_all_years"): (0.0567, 0.0001),
    ("b", "aum_share_without_fee_min_year"): (0.0327, 0.0001),
    ("b", "aum_share_without_fee_max_year"): (0.0600, 0.0001),
    ("b", "zero_amount_fee_rows"): (0, 0),
    ("b", "groups_without_unbilled_months"): (0, 0),
    ("b", "advisory_fee_txn_rate_unbilled_months"): (0.230, 0.001),
    ("b", "advisory_fee_txn_rate_billed_months"): (0.235, 0.001),
    ("b", "onboarding_months_in_data"): (968, 0),
    ("b", "onboarding_months_unbilled"): (72, 0),
    ("b", "onboarding_months_unbilled_rate"): (0.0744, 0.0001),
    # (c) AUM-Weighted Alpha, Dec 2024 snapshot
    ("c", "weighted_alpha_excl_suspects"): (0.014480, 0.000001),
    ("c", "simple_mean_alpha_excl_suspects"): (0.008788, 0.000001),
    ("c", "weighted_alpha_incl_suspects"): (0.016678, 0.000001),
    ("c", "simple_mean_alpha_incl_suspects"): (0.155624, 0.000001),
    ("c", "suspect_rows_last_snapshot"): (148, 0),
    ("c", "suspect_alpha_max"): (71.337772, 0.000001),
    ("c", "suspect_alpha_median"): (0.535597, 0.000001),
    ("c", "non_suspect_alpha_max_abs"): (0.498245, 0.000001),
    ("c", "suspect_rows_all_years"): (3_875, 0),
    ("c", "suspect_rows_share_retail"): (1.0, 0),
    ("c", "retail_weighted_alpha_excl_suspects"): (0.024041, 0.000001),
    ("c", "retail_weighted_alpha_incl_suspects"): (0.076224, 0.000001),
    ("c", "alpha_signal_changes_firm"): (0, 0),
    ("c", "alpha_signal_changes_retail"): (0, 0),
    ("c", "weighted_alpha_jan_2024"): (-0.000092, 0.000001),
    ("c", "weighted_alpha_dec_2024"): (0.014480, 0.000001),
    # The mistake: averaging a year-to-date figure over the 12 months of the year.
    ("c", "mean_of_12_monthly_alphas_2024"): (0.002982, 0.000001),
    ("c", "understatement_factor"): (4.86, 0.01),
    # (d) firm-wide context for the tier table
    ("d", "firm_net_flows_2024"): (77_513_055.26, 0.01),
    ("d", "retail_share_of_net_flows"): (0.5700, 0.0001),
    ("d", "retail_share_of_ending_aum"): (0.0419, 0.0001),
    ("d", "retail_start_aum"): (447_795_648.67, 0.01),
}
TIER_EXPECTED = {
    # (d) 2024 by tier: organic growth, total growth, net flows, gross flows, remainder
    "HNW":    dict(ogr=0.0118, yoy=0.1964, net_flows=25_227_406, deposits_pct=0.0563,
                   withdrawals_pct=0.0445, other_growth=0.1846, clients_gained=0, clients_lost=0),
    "Retail": dict(ogr=0.0987, yoy=0.1913, net_flows=44_184_048, deposits_pct=0.5478,
                   withdrawals_pct=0.4491, other_growth=0.0926, clients_gained=0, clients_lost=0),
    "UHNW":   dict(ogr=0.0010, yoy=0.1959, net_flows=8_101_601, deposits_pct=0.0056,
                   withdrawals_pct=0.0046, other_growth=0.1949, clients_gained=0, clients_lost=0),
}
TIER_TOLERANCE = dict(ogr=0.0001, yoy=0.0001, net_flows=1, deposits_pct=0.0001,
                      withdrawals_pct=0.0001, other_growth=0.0001, clients_gained=0, clients_lost=0)
SIGNAL_THRESHOLD = 0.02


class DesignQuestionError(Exception):
    pass


# ── Data ──────────────────────────────────────────────────────────────────────
def read(name, dates=(), numeric=()):
    path = DATA_DIR / f"{name}.csv"
    if not path.exists():
        raise DesignQuestionError(f"Missing data file: {path}")
    df = pd.read_csv(path)
    for col in dates:
        parsed = pd.to_datetime(df[col], format="%Y-%m-%d", errors="coerce")
        if parsed.isna().any():
            raise DesignQuestionError(f"{name}: {col} has blank or non-ISO dates")
        df[col] = parsed
    for col in numeric:
        values = pd.to_numeric(df[col], errors="coerce")
        if values.isna().any():
            raise DesignQuestionError(f"{name}: {col} has blank or non-numeric values")
        df[col] = values
    return df


def with_tier(df, clients, name):
    df = df.merge(clients[["client_id", "client_tier"]], on="client_id", how="left",
                  validate="many_to_one")
    if df.client_tier.isna().any():
        raise DesignQuestionError(f"{name}: client_id not found in dim_client")
    return df


def on_keys(left, left_keys, right, right_keys):
    """True where the left row's key pair appears in the right table (vectorized membership)."""
    return pd.MultiIndex.from_frame(left[left_keys]).isin(
        pd.MultiIndex.from_frame(right[right_keys].set_axis(left_keys, axis=1)))


def load():
    clients = read("dim_client", dates=["client_since"])
    if clients.client_id.duplicated().any() or clients.client_tier.isna().any():
        raise DesignQuestionError("dim_client must have one row and a tier per client_id")
    snaps = with_tier(read("fact_portfolio_snapshot", dates=["snapshot_date"],
                           numeric=["aum", "active_alpha_ytd", "is_return_suspect"]),
                      clients, "snapshots")
    fees = read("fact_fees", dates=["fee_date"], numeric=["amount", "aum_basis"])
    txns = with_tier(read("fact_transactions", dates=["txn_date"], numeric=["amount"]),
                     clients, "transactions")

    if not snaps.is_return_suspect.isin([0, 1]).all():
        raise DesignQuestionError("snapshots: is_return_suspect must be 0 or 1")
    if snaps.duplicated(["client_id", "snapshot_date"]).any():
        raise DesignQuestionError("snapshot grain broken: more than one row per client per month")
    if fees.duplicated(["client_id", "fee_date"]).any():
        raise DesignQuestionError("more than one fee row per client per month; (b) assumes one")
    # Same rule as Power BI and 01_reconcile_measures.py: text comparison ignores case.
    txns["txn_type"] = txns.txn_type.str.casefold()
    return clients, snaps, fees, txns


def weighted_alpha(rows):
    return (rows.aum * rows.active_alpha_ytd).sum() / rows.aum.sum()


def signal(alpha):
    return "Outperforming" if alpha >= SIGNAL_THRESHOLD else "Lagging" if alpha <= -SIGNAL_THRESHOLD else "In line"


# ── Questions ─────────────────────────────────────────────────────────────────
def question_a(clients, snaps):
    last_date = snaps.snapshot_date.max()
    on_last = snaps[snaps.snapshot_date.eq(last_date)]
    # SUMX ( VALUES ( dim_client[client_id] ), [Ending AUM] ): each client's own last balance.
    own_last = snaps.sort_values("snapshot_date").groupby("client_id").tail(1)
    departed = own_last[own_last.snapshot_date.lt(last_date)]
    inactive = set(clients.loc[clients.is_active.astype(str).str.lower().eq("false"), "client_id"])
    difference = own_last.aum.sum() - on_last.aum.sum()
    return {
        "ending_aum": on_last.aum.sum(),
        "sumx_client_ending_aum": own_last.aum.sum(),
        "difference": difference,
        "difference_pct_of_ending_aum": difference / on_last.aum.sum(),
        "ending_clients": on_last.client_id.nunique(),
        "departed_clients": len(departed),
        "departed_clients_last_balance": departed.aum.sum(),
        # By construction the gap is the departed clients' balances; checked, not assumed.
        "difference_equals_departed_balance": int(abs(difference - departed.aum.sum()) < 0.005),
        "departed_in_2022": int(departed.snapshot_date.dt.year.eq(2022).sum()),
        "departed_in_2023": int(departed.snapshot_date.dt.year.eq(2023).sum()),
        "departed_flagged_inactive": int(departed.client_id.isin(inactive).sum()),
    }


def question_b(clients, snaps, fees, txns):
    snaps = snaps.merge(clients[["client_id", "primary_account_type", "risk_profile", "client_since"]],
                        on="client_id", how="left", validate="many_to_one")
    snaps["billed"] = on_keys(snaps, ["client_id", "snapshot_date"], fees, ["client_id", "fee_date"])
    s24 = snaps[snaps.snapshot_date.dt.year.eq(2024)]
    f24 = fees[fees.fee_date.dt.year.eq(2024)]
    fees_2024 = f24.amount.sum()

    # On every billed month, the fee's aum_basis is the snapshot's aum.
    matched = s24[s24.billed].merge(f24, left_on=["client_id", "snapshot_date"],
                                    right_on=["client_id", "fee_date"], validate="one_to_one")
    year = snaps.snapshot_date.dt.year
    share_by_year = snaps.groupby(year).apply(lambda g: g.loc[~g.billed, "aum"].sum() / g.aum.sum())
    # The gap is everywhere: every tier, account type, risk profile and year has unbilled months.
    groups = [snaps.client_tier, snaps.account_type, snaps.risk_profile, year]
    groups_without_unbilled = sum(int((~snaps.billed).groupby(g).sum().eq(0).sum()) for g in groups)

    # Was a fee taken anyway? An Advisory Fee debit in the same month would say so.
    debits = txns[txns.txn_type.eq("advisory fee")].assign(
        month=lambda t: t.txn_date.dt.to_period("M").dt.to_timestamp())
    has_debit = on_keys(snaps, ["client_id", "snapshot_date"], debits, ["client_id", "month"])
    # Onboarding month = the snapshot month containing client_since (only for clients who
    # joined inside the data's date range; earlier clients' first snapshot is just Jan 2020).
    onboarding = snaps.snapshot_date.eq(snaps.client_since.dt.to_period("M").dt.to_timestamp())

    fy = fees_2024 * 12 * 10000 / s24.aum.sum()
    efr = fees_2024 * 12 * 10000 / f24.aum_basis.sum()
    return {
        "fee_yield_bps_2024": fy,
        "effective_fee_rate_bps_2024": efr,
        "gap_bps_2024": efr - fy,
        "snapshot_months_2024": len(s24),
        "billed_months_2024": len(matched),
        "snapshot_months_without_fee_2024": int((~s24.billed).sum()),
        "months_share_without_fee_2024": (~s24.billed).mean(),
        "aum_share_without_fee_2024": s24.loc[~s24.billed, "aum"].sum() / s24.aum.sum(),
        "billed_months_aum_basis_equals_aum": (matched.aum_basis - matched.aum).abs().le(0.005).mean(),
        "fee_yield_bps_2024_billed_months_only": fees_2024 * 12 * 10000 / s24.loc[s24.billed, "aum"].sum(),
        "snapshot_months_all_years": len(snaps),
        "snapshot_months_without_fee_all_years": int((~snaps.billed).sum()),
        "months_share_without_fee_all_years": (~snaps.billed).mean(),
        "aum_share_without_fee_min_year": share_by_year.min(),
        "aum_share_without_fee_max_year": share_by_year.max(),
        "zero_amount_fee_rows": int(fees.amount.eq(0).sum()),
        "groups_without_unbilled_months": groups_without_unbilled,
        "advisory_fee_txn_rate_unbilled_months": has_debit[~snaps.billed.to_numpy()].mean(),
        "advisory_fee_txn_rate_billed_months": has_debit[snaps.billed.to_numpy()].mean(),
        "onboarding_months_in_data": int(onboarding.sum()),
        "onboarding_months_unbilled": int((onboarding & ~snaps.billed).sum()),
        "onboarding_months_unbilled_rate": (~snaps.billed[onboarding]).mean(),
    }


def question_c(snaps):
    last = snaps[snaps.snapshot_date.eq(snaps.snapshot_date.max())]
    valid, suspect = last[last.is_return_suspect.eq(0)], last[last.is_return_suspect.eq(1)]
    retail = last[last.client_tier.eq("Retail")]
    retail_valid = retail[retail.is_return_suspect.eq(0)]
    year_2024 = snaps[snaps.snapshot_date.dt.year.eq(2024) & snaps.is_return_suspect.eq(0)]
    monthly = year_2024.groupby("snapshot_date").apply(weighted_alpha)
    if len(monthly) != 12:
        raise DesignQuestionError(f"expected 12 snapshot months in 2024, found {len(monthly)}")
    all_suspects = snaps[snaps.is_return_suspect.eq(1)]
    return {
        "weighted_alpha_excl_suspects": weighted_alpha(valid),
        "simple_mean_alpha_excl_suspects": valid.active_alpha_ytd.mean(),
        "weighted_alpha_incl_suspects": weighted_alpha(last),
        "simple_mean_alpha_incl_suspects": last.active_alpha_ytd.mean(),
        "suspect_rows_last_snapshot": len(suspect),
        "suspect_alpha_max": suspect.active_alpha_ytd.max(),
        "suspect_alpha_median": suspect.active_alpha_ytd.median(),
        "non_suspect_alpha_max_abs": valid.active_alpha_ytd.abs().max(),
        "suspect_rows_all_years": len(all_suspects),
        "suspect_rows_share_retail": all_suspects.client_tier.eq("Retail").mean(),
        "retail_weighted_alpha_excl_suspects": weighted_alpha(retail_valid),
        "retail_weighted_alpha_incl_suspects": weighted_alpha(retail),
        "alpha_signal_changes_firm": int(signal(weighted_alpha(valid)) != signal(weighted_alpha(last))),
        "alpha_signal_changes_retail": int(signal(weighted_alpha(retail_valid)) != signal(weighted_alpha(retail))),
        "weighted_alpha_jan_2024": monthly.loc["2024-01-01"],
        "weighted_alpha_dec_2024": monthly.loc["2024-12-01"],
        "mean_of_12_monthly_alphas_2024": monthly.mean(),
        "understatement_factor": monthly.loc["2024-12-01"] / monthly.mean(),
    }


def question_d(snaps, txns):
    dec_2023 = snaps[snaps.snapshot_date.eq("2023-12-01")]
    dec_2024 = snaps[snaps.snapshot_date.eq("2024-12-01")]
    t24 = txns[txns.txn_date.dt.year.eq(2024)]
    tiers, firm = {}, {}
    for tier in sorted(TIER_EXPECTED):
        start, end = dec_2023[dec_2023.client_tier.eq(tier)], dec_2024[dec_2024.client_tier.eq(tier)]
        tt = t24[t24.client_tier.eq(tier)]
        deposits = tt.loc[tt.txn_type.eq("deposit"), "amount"].sum()
        withdrawals = tt.loc[tt.txn_type.eq("withdrawal"), "amount"].sum()
        ly, ending = start.aum.sum(), end.aum.sum()
        tiers[tier] = dict(
            ogr=(deposits - withdrawals) / ly,
            yoy=ending / ly - 1,
            net_flows=deposits - withdrawals,
            deposits_pct=deposits / ly,
            withdrawals_pct=withdrawals / ly,
            # What total growth leaves after net flows: market returns and anything else.
            other_growth=(ending - ly - (deposits - withdrawals)) / ly,
            clients_gained=int((~end.client_id.isin(start.client_id)).sum()),
            clients_lost=int((~start.client_id.isin(end.client_id)).sum()),
        )
    firm_flows = sum(t["net_flows"] for t in tiers.values())
    firm = {
        "firm_net_flows_2024": firm_flows,
        "retail_share_of_net_flows": tiers["Retail"]["net_flows"] / firm_flows,
        "retail_share_of_ending_aum": dec_2024.loc[dec_2024.client_tier.eq("Retail"), "aum"].sum()
                                      / dec_2024.aum.sum(),
        "retail_start_aum": dec_2023.loc[dec_2023.client_tier.eq("Retail"), "aum"].sum(),
    }
    return tiers, firm


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    # A failed run must not leave an earlier, now-unconfirmed evidence file looking current.
    OUTPUT.unlink(missing_ok=True)
    clients, snaps, fees, txns = load()

    results = {}
    tiers, firm = question_d(snaps, txns)
    for q, figures in [("a", question_a(clients, snaps)), ("b", question_b(clients, snaps, fees, txns)),
                       ("c", question_c(snaps)), ("d", firm)]:
        results.update({(q, k): v for k, v in figures.items()})
    for tier, figures in tiers.items():
        results.update({("d", f"{tier}_{k}"): v for k, v in figures.items()})

    expected = dict(EXPECTED)
    for tier, figures in TIER_EXPECTED.items():
        expected.update({("d", f"{tier}_{k}"): (v, TIER_TOLERANCE[k]) for k, v in figures.items()})

    failures = []
    for key, (want, tol) in expected.items():
        got = results.get(key)
        if got is None or pd.isna(got) or abs(got - want) > tol:
            failures.append(f"{key[0]}) {key[1]}: expected {want}, got {got}")
    unpinned = sorted(set(results) - set(expected))
    if unpinned:
        failures.append(f"figures computed but not pinned: {unpinned}")

    report = pd.DataFrame([(q, name, value) for (q, name), value in results.items()],
                          columns=["question", "figure", "value"])
    for q in "abcd":
        print(f"\n({q})")
        for row in report[report.question.eq(q)].itertuples():
            print(f"   {row.figure:<42} {row.value:,.6f}" if abs(row.value) < 1000
                  else f"   {row.figure:<42} {row.value:,.2f}")
    if failures:
        print("\n   report NOT written")
        raise DesignQuestionError(f"{len(failures)} figure(s) changed: " + "; ".join(failures))
    OUTPUT.parent.mkdir(exist_ok=True)
    report.to_csv(OUTPUT, index=False)
    print(f"\n   wrote {OUTPUT}")
    print(f"   all {len(expected)} quoted figures confirmed")


if __name__ == "__main__":
    try:
        main()
    except DesignQuestionError as err:
        print(f"DesignQuestionError: {err}")
        sys.exit(1 if "changed" in str(err) else 2)
