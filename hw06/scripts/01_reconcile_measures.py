# 01_reconcile_measures.py
# HW6 Part B: recompute every Power BI measure independently in pandas from the
# Wildcat Capital Clean CSVs, compare with the values exported from Power BI
# (reports/powerbi_values.csv), and write reports/measure_reconciliation.csv.
# The pandas side never reads powerbi_values.csv; that file is only compared against.
# Author: Jonah Karst
# Generated: 2026-11-09
#
# Run from the repo root:  python hw06/scripts/01_reconcile_measures.py
# Exit codes: 0 all rows match, 1 at least one mismatch, 2 bad input (nothing written).

import sys
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np
import pandas as pd

HW_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = HW_DIR / "data" / "clean"
REPORTS_DIR = HW_DIR / "reports"
POWERBI_VALUES = REPORTS_DIR / "powerbi_values.csv"
OUTPUT = REPORTS_DIR / "measure_reconciliation.csv"

# Measure -> comparison class. Tolerances follow the brief: 0.01 for currency,
# 0.0001 for ratios; a client count and a text label must match exactly.
CURRENCY = ["Total Fees", "Net Flows", "AUM (naive SUM)", "Ending AUM", "Ending AUM LY",
            "Ending AUM PM", "Avg AUM per Client", "Avg Monthly AUM"]
RATIO = ["AUM YoY %", "AUM MoM %", "Fee Yield (bps)", "Organic Growth Rate",
         "AUM-Weighted Alpha", "Top 10 Client Share"]
COUNT = ["Ending Clients"]
TEXT = ["Alpha Signal"]
TOLERANCE = {**{m: 0.01 for m in CURRENCY}, **{m: 0.0001 for m in RATIO}, **{m: 0 for m in COUNT}}
ALL_MEASURES = CURRENCY + RATIO + COUNT + TEXT

# Required coverage (brief, Part B): every measure at the grand total; measures 1, 4, 6-10
# by year; measures 1, 3, 4, 7-11 by client tier for 2024; measure 5 for December 2024;
# and the naive SUM next to them.
BY_YEAR = ["AUM (naive SUM)", "Ending AUM", "Ending AUM LY", "AUM YoY %", "Avg Monthly AUM",
           "Fee Yield (bps)", "Organic Growth Rate", "AUM-Weighted Alpha", "Alpha Signal"]
BY_TIER_2024 = ["Ending AUM", "Avg AUM per Client", "Ending AUM LY", "AUM YoY %", "Fee Yield (bps)",
                "Organic Growth Rate", "AUM-Weighted Alpha", "Alpha Signal", "Top 10 Client Share"]
DEC_2024 = ["Ending AUM PM", "AUM MoM %"]

SIGNAL_THRESHOLD = 0.02   # Alpha Signal: >= +2% Outperforming, <= -2% Lagging
TOP_N = 10


class ReconcileError(Exception):
    pass


# ── Slices ────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Slice:
    """A filter context: an inclusive date window, optionally one client tier."""
    start: pd.Timestamp
    end: pd.Timestamp
    tier: str | None = None

    def shift(self, years=0, months=0):
        """The same slice moved back in time, like SAMEPERIODLASTYEAR / DATEADD.

        DateOffset clips to a shorter month (Dec 31 -> Nov 30), but a window ending on a
        month end must still end on one after the shift: Nov 1-30 -> Oct 1-31, not Oct 1-30.
        A window ending mid-month keeps the same day.
        """
        offset = pd.DateOffset(years=years, months=months)
        end = self.end - offset
        if self.end.is_month_end:
            end += pd.offsets.MonthEnd(0)
        return replace(self, start=self.start - offset, end=end)


def parse_slice(label, calendar_start, calendar_end, tiers):
    """'total' | 'year=YYYY' | 'year=YYYY|client_tier=T' | 'month=YYYY-MM' -> Slice."""
    if label == "total":
        return Slice(calendar_start, calendar_end)
    parts = dict(p.split("=", 1) for p in label.split("|") if "=" in p)
    if len(parts) != label.count("|") + 1 or set(parts) - {"year", "month", "client_tier"}:
        raise ReconcileError(f"Unrecognized slice label: {label!r}")
    if ("year" in parts) == ("month" in parts):
        raise ReconcileError(f"Slice needs exactly one of year= or month=: {label!r}")
    if "year" in parts:
        if not parts["year"].isdigit():
            raise ReconcileError(f"Bad year in slice {label!r}")
        start = pd.Timestamp(year=int(parts["year"]), month=1, day=1)
        end = pd.Timestamp(year=int(parts["year"]), month=12, day=31)
    else:
        start = pd.to_datetime(parts["month"], format="%Y-%m", errors="coerce")
        if pd.isna(start):
            raise ReconcileError(f"Bad month in slice {label!r}")
        end = start + pd.offsets.MonthEnd(0)
    tier = parts.get("client_tier")
    if tier is not None and tier not in tiers:
        raise ReconcileError(f"Unknown client_tier in slice {label!r}")
    return Slice(start, end, tier)


# ── Data ──────────────────────────────────────────────────────────────────────
def read_csv(name, columns):
    path = DATA_DIR / f"{name}.csv"
    if not path.exists():
        raise ReconcileError(f"Missing data file: {path}")
    return pd.read_csv(path, usecols=columns)


def parse_dates(df, col, name):
    dates = pd.to_datetime(df[col], format="%Y-%m-%d", errors="coerce")
    if dates.isna().any():
        raise ReconcileError(f"{name}: {col} has blank or non-ISO dates")
    return dates


def require_numeric(df, cols, name):
    """Every value present and numeric, so a SUM can't silently become 0 or text."""
    for col in cols:
        values = pd.to_numeric(df[col], errors="coerce")
        if values.isna().any():
            raise ReconcileError(f"{name}: {col} has {int(values.isna().sum())} blank or "
                                 f"non-numeric values")
        df[col] = values


def load_data():
    clients = read_csv("dim_client", ["client_id", "client_tier"])
    calendar = read_csv("dim_date", ["date"])
    snapshots = read_csv("fact_portfolio_snapshot", ["client_id", "snapshot_date", "aum",
                                                     "active_alpha_ytd", "is_return_suspect"])
    fees = read_csv("fact_fees", ["client_id", "fee_date", "amount"])
    txns = read_csv("fact_transactions", ["client_id", "txn_date", "txn_type", "amount"])

    if clients.client_id.duplicated().any() or clients.client_tier.isna().any():
        raise ReconcileError("dim_client must have one row and a tier per client_id")
    calendar_dates = parse_dates(calendar, "date", "dim_date")

    require_numeric(snapshots, ["aum", "active_alpha_ytd", "is_return_suspect"], "snapshots")
    require_numeric(fees, ["amount"], "fees")
    require_numeric(txns, ["amount"], "transactions")

    facts = {}
    for name, df, date_col in [("snapshots", snapshots, "snapshot_date"),
                               ("fees", fees, "fee_date"), ("txns", txns, "txn_date")]:
        df[date_col] = parse_dates(df, date_col, name)
        # Power BI reaches dim_date through this date. A fact date outside the calendar would
        # still count in an unfiltered DAX SUM but be dropped by the pandas date window.
        outside = ~df[date_col].isin(calendar_dates)
        if outside.any():
            raise ReconcileError(f"{name}: {int(outside.sum())} {date_col} values not in dim_date")
        # Tier comes from dim_client, as it does through the client relationship in Power BI.
        df = df.merge(clients, on="client_id", how="left", validate="many_to_one")
        if df.client_tier.isna().any():
            raise ReconcileError(f"{name}: client_id not found in dim_client")
        facts[name] = df.rename(columns={date_col: "date"})

    snaps = facts["snapshots"]
    if not snaps.is_return_suspect.isin([0, 1]).all():
        raise ReconcileError("snapshots: is_return_suspect must be 0 or 1")
    if snaps.duplicated(["client_id", "date"]).any():
        raise ReconcileError("snapshots: more than one row per client per date (grain broken)")
    # DAX compares text without regard to case: txn_type = "Deposit" also matches "deposit".
    txn_type = facts["txns"].txn_type.str.casefold()
    if not {"deposit", "withdrawal"} <= set(txn_type):
        raise ReconcileError("transactions: Deposit or Withdrawal type missing")
    facts["txns"] = facts["txns"].assign(txn_type=txn_type)

    return facts, calendar_dates.min(), calendar_dates.max(), sorted(clients.client_tier.unique())


# ── Measures (pandas twins of the DAX in powerbi/measures.md) ─────────────────
def divide(numerator, denominator):
    """DAX DIVIDE: blank when either side is blank or the denominator is 0."""
    if pd.isna(numerator) or pd.isna(denominator) or denominator == 0:
        return np.nan
    return numerator / denominator


def rows_in(df, s):
    mask = df.date.between(s.start, s.end)
    if s.tier is not None:
        mask &= df.client_tier.eq(s.tier)
    return df[mask]


def blank_sum(series):
    """SUM over no rows is BLANK in DAX, not 0."""
    return series.sum() if len(series) else np.nan


class Measures:
    def __init__(self, facts):
        self.snaps, self.fees, self.txns = facts["snapshots"], facts["fees"], facts["txns"]
        self.by_name = {
            "Total Fees": self.total_fees, "Net Flows": self.net_flows,
            "AUM (naive SUM)": self.naive_sum, "Ending AUM": self.ending_aum,
            "Ending Clients": self.ending_clients, "Avg AUM per Client": self.avg_aum_per_client,
            "Ending AUM LY": self.ending_aum_ly, "AUM YoY %": self.aum_yoy,
            "Ending AUM PM": self.ending_aum_pm, "AUM MoM %": self.aum_mom,
            "Avg Monthly AUM": self.avg_monthly_aum, "Fee Yield (bps)": self.fee_yield_bps,
            "Organic Growth Rate": self.organic_growth_rate,
            "AUM-Weighted Alpha": self.aum_weighted_alpha, "Alpha Signal": self.alpha_signal,
            "Top 10 Client Share": self.top10_client_share,
        }
        if set(self.by_name) != set(ALL_MEASURES):
            raise ReconcileError("Measure list and pandas twins are out of step")

    def last_snapshot_rows(self, s):
        """Snapshot rows on the last date that has data in the slice (LASTNONBLANK)."""
        snaps = rows_in(self.snaps, s)
        return snaps[snaps.date.eq(snaps.date.max())] if len(snaps) else snaps

    def total_fees(self, s):
        return blank_sum(rows_in(self.fees, s).amount)

    def net_flows(self, s):
        txns = rows_in(self.txns, s)
        deposits = blank_sum(txns.loc[txns.txn_type.eq("deposit"), "amount"])
        withdrawals = blank_sum(txns.loc[txns.txn_type.eq("withdrawal"), "amount"])
        if pd.isna(deposits) and pd.isna(withdrawals):
            return np.nan
        return np.nan_to_num(deposits) - np.nan_to_num(withdrawals)

    def naive_sum(self, s):
        return blank_sum(rows_in(self.snaps, s).aum)

    def ending_aum(self, s):
        return blank_sum(self.last_snapshot_rows(s).aum)

    def ending_clients(self, s):
        last = self.last_snapshot_rows(s)
        return last.client_id.nunique() if len(last) else np.nan

    def avg_aum_per_client(self, s):
        return divide(self.ending_aum(s), self.ending_clients(s))

    def ending_aum_ly(self, s):
        return self.ending_aum(s.shift(years=1))

    def aum_yoy(self, s):
        ly = self.ending_aum_ly(s)
        return divide(self.ending_aum(s) - ly, ly)

    def ending_aum_pm(self, s):
        return self.ending_aum(s.shift(months=1))

    def aum_mom(self, s):
        pm = self.ending_aum_pm(s)
        return divide(self.ending_aum(s) - pm, pm)

    def avg_monthly_aum(self, s):
        return divide(self.naive_sum(s), rows_in(self.snaps, s).date.nunique())

    def fee_yield_bps(self, s):
        return divide(self.total_fees(s) * 12 * 10000, self.naive_sum(s))

    def organic_growth_rate(self, s):
        return divide(self.net_flows(s), self.ending_aum_ly(s))

    def aum_weighted_alpha(self, s):
        # Last date is chosen from all rows, then suspect returns are excluded.
        last = self.last_snapshot_rows(s)
        valid = last[last.is_return_suspect.eq(0)]
        return divide(blank_sum(valid.aum * valid.active_alpha_ytd), blank_sum(valid.aum))

    def alpha_signal(self, s):
        alpha = self.aum_weighted_alpha(s)
        if pd.isna(alpha):
            return ""
        if alpha >= SIGNAL_THRESHOLD:
            return "Outperforming"
        if alpha <= -SIGNAL_THRESHOLD:
            return "Lagging"
        return "In line"

    def top10_client_share(self, s):
        last = self.last_snapshot_rows(s)
        by_client = last.groupby("client_id").aum.sum()
        # DAX TOPN keeps every row tied at the cutoff, so a tie at rank 10 returns 11 clients.
        return divide(by_client.nlargest(TOP_N, keep="all").sum(), blank_sum(by_client))

    def compute(self, measure, s):
        return self.by_name[measure](s)


# ── Power BI values and comparison ────────────────────────────────────────────
def load_powerbi_values(years, tiers):
    if not POWERBI_VALUES.exists():
        raise ReconcileError(f"Missing {POWERBI_VALUES}")
    pbi = pd.read_csv(POWERBI_VALUES, dtype=str, keep_default_na=False)
    if list(pbi.columns) != ["measure", "slice", "value"]:
        raise ReconcileError(f"{POWERBI_VALUES.name} must have columns measure, slice, value; "
                             f"found {list(pbi.columns)}")
    pbi = pbi.apply(lambda col: col.str.strip())

    unknown = sorted(set(pbi.measure) - set(ALL_MEASURES))
    if unknown:
        raise ReconcileError(f"Measures with no pandas twin: {unknown}")
    dupes = pbi[pbi.duplicated(["measure", "slice"], keep=False)]
    if len(dupes):
        raise ReconcileError(f"Duplicate measure+slice rows: {dupes.values.tolist()}")

    required = {(m, "total") for m in ALL_MEASURES}
    required |= {(m, f"year={y}") for y in years for m in BY_YEAR}
    required |= {(m, f"year=2024|client_tier={t}") for t in tiers for m in BY_TIER_2024}
    required |= {(m, "month=2024-12") for m in DEC_2024}
    missing = sorted(required - set(zip(pbi.measure, pbi.slice)))
    if missing:
        raise ReconcileError(f"{len(missing)} required measure/slice rows missing: {missing}")
    return pbi


def compare(measure, powerbi_text, pandas_value):
    """Return (powerbi_value, pandas_value, abs_diff, match) for one row."""
    if measure in TEXT:
        pandas_text = pandas_value or ""
        return powerbi_text, pandas_text, np.nan, powerbi_text == pandas_text
    try:
        powerbi_value = float(powerbi_text) if powerbi_text else np.nan
    except ValueError:
        raise ReconcileError(f"{measure}: Power BI value {powerbi_text!r} is not a number") from None
    pandas_value = float(pandas_value) if not pd.isna(pandas_value) else np.nan
    if pd.isna(powerbi_value) or pd.isna(pandas_value):
        # Blank vs blank matches (e.g., 2020 has no prior year); blank vs a number does not.
        return powerbi_value, pandas_value, np.nan, pd.isna(powerbi_value) and pd.isna(pandas_value)
    diff = abs(powerbi_value - pandas_value)
    return powerbi_value, pandas_value, diff, bool(diff <= TOLERANCE[measure])


def main():
    # A failed run must not leave the previous run's all-matched report looking current.
    OUTPUT.unlink(missing_ok=True)

    facts, calendar_start, calendar_end, tiers = load_data()
    years = list(range(calendar_start.year, calendar_end.year + 1))
    pbi = load_powerbi_values(years, tiers)
    measures = Measures(facts)

    rows, alpha_margins = [], []
    for measure, label, powerbi_text in pbi.itertuples(index=False):
        s = parse_slice(label, calendar_start, calendar_end, tiers)
        rows.append((measure, label, *compare(measure, powerbi_text, measures.compute(measure, s))))
        if measure in TEXT:
            alpha = measures.aum_weighted_alpha(s)
            if not pd.isna(alpha):
                alpha_margins.append(abs(abs(alpha) - SIGNAL_THRESHOLD))
    result = pd.DataFrame(rows, columns=["measure", "slice", "powerbi_value", "pandas_value",
                                         "abs_diff", "match"])

    REPORTS_DIR.mkdir(exist_ok=True)
    result.to_csv(OUTPUT, index=False)

    mismatches = result[~result.match]
    print(f"HW6 Part B reconciliation - {POWERBI_VALUES.name} vs pandas")
    print(f"   rows checked: {len(result)}  (slices: {result.slice.nunique()}, "
          f"measures: {result.measure.nunique()})")
    print(f"   rows matched: {int(result.match.sum())}")
    largest = result.dropna(subset=["abs_diff"]).groupby("measure").abs_diff.max()
    print("   largest abs_diff by measure:")
    for measure, diff in largest.items():
        print(f"      {measure:<22} {diff:.3g}  (tolerance {TOLERANCE[measure]})")
    # Alpha Signal is compared exactly. That is safe only while no alpha sits within the
    # alpha tolerance of the +/-2% threshold, where float noise could flip the label.
    if alpha_margins:
        closest = min(alpha_margins)
        print(f"   closest AUM-Weighted Alpha to the +/-2% Alpha Signal threshold: {closest:.4f} "
              f"({'safe' if closest > TOLERANCE['AUM-Weighted Alpha'] else 'BORDERLINE'})")
    naive, ending = (result.set_index(["measure", "slice"]).pandas_value
                     .loc[[("AUM (naive SUM)", "total"), ("Ending AUM", "total")]])
    print(f"   naive SUM / Ending AUM at the grand total: {naive / ending:.1f}x "
          f"(both tools make the same mistake)")
    print(f"   wrote {OUTPUT}")
    if len(mismatches):
        print(f"\n   {len(mismatches)} MISMATCH(ES):")
        print(mismatches.to_string(index=False))
        sys.exit(1)
    print("   all rows match")


if __name__ == "__main__":
    try:
        main()
    except ReconcileError as err:
        print(f"ReconcileError: {err}")
        sys.exit(2)
