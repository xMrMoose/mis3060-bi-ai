"""
hw03_timeline.py

Purpose:     Join the executive events table to the earnings table to build a
             corporate events timeline. For every executive event, find the
             nearest earnings filing for the same company, measure the gap in
             days, and label the event as before / after / same week as that
             earnings announcement.
Inputs:      hw03/earnings_history.csv     (from hw03_earnings.py)
             hw03/executive_events.csv     (from hw03_executives.py)
Output:      hw03/corporate_events_timeline.csv
Author:      Jonah Karst
Generated:   2026-09-29

Run from the command line:
    python hw03/hw03_timeline.py

Columns in the output:
  * every column from executive_events.csv (company, ticker, cik, filing_date,
    event_type, person_name, title, effective_date)
  * every remaining column from earnings_history.csv for the nearest earnings
    filing. company, ticker, and cik already appear above (identical values),
    so they are not repeated; the earnings table's filing_date would collide
    with the event's filing_date, so it is named earnings_filing_date.
  * days_to_nearest_earnings  - whole days between the event's filing_date and
    the nearest earnings filing_date (always zero or positive)
  * event_timing              - 'before earnings', 'after earnings', or
    'same week' (within 7 days of the nearest earnings filing)
"""

import sys
from pathlib import Path

import pandas as pd

# Keep printing safe on Windows consoles.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
EARNINGS_PATH = BASE_DIR / "earnings_history.csv"
EVENTS_PATH = BASE_DIR / "executive_events.csv"
OUTPUT_PATH = BASE_DIR / "corporate_events_timeline.csv"

SAME_WEEK_DAYS = 7           # within this many days of an earnings filing = 'same week'
NOT_FOUND = "NOT_FOUND"
TICKER_ORDER = ["AAPL", "MSFT", "NVDA", "JPM", "WMT"]

EVENT_COLUMNS = ["company", "ticker", "cik", "filing_date",
                 "event_type", "person_name", "title", "effective_date"]
EARNINGS_COLUMNS = ["earnings_filing_date", "period", "revenue_reported", "eps_diluted", "net_income"]
NEW_COLUMNS = ["days_to_nearest_earnings", "event_timing"]
OUTPUT_COLUMNS = EVENT_COLUMNS + EARNINGS_COLUMNS + NEW_COLUMNS


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------
def load_csv(path, label):
    """Read a CSV keeping every value as text (so CIKs keep leading zeros and
    NOT_FOUND stays a plain string), or exit with a clear message."""
    if not path.exists():
        sys.exit(f"ERROR: {label} not found at {path}. Run the script that creates it first.")
    return pd.read_csv(path, dtype=str, keep_default_na=False)


# ---------------------------------------------------------------------------
# Join logic
# ---------------------------------------------------------------------------
def classify(event_date, earnings_date):
    """Return (days_to_nearest_earnings, event_timing) for two dates."""
    gap = (earnings_date - event_date).days      # positive: earnings came after the event
    days = abs(gap)
    if days <= SAME_WEEK_DAYS:
        timing = "same week"
    elif gap > 0:
        timing = "before earnings"               # event came before the earnings filing
    else:
        timing = "after earnings"                # event came after the earnings filing
    return days, timing


def build_timeline(events, earnings):
    """One output row per executive event, joined to its nearest earnings filing."""
    earnings = earnings.copy()
    earnings["_date"] = pd.to_datetime(earnings["filing_date"], errors="coerce")
    earnings = earnings.dropna(subset=["_date"]).sort_values("_date")   # earliest first: ties go to the earlier filing

    rows = []
    for _, event in events.iterrows():
        row = {column: event[column] for column in EVENT_COLUMNS}
        row.update({column: NOT_FOUND for column in EARNINGS_COLUMNS + NEW_COLUMNS})

        event_date = pd.to_datetime(event["filing_date"], errors="coerce")
        company_earnings = earnings[earnings["ticker"] == event["ticker"]]
        if pd.isna(event_date) or company_earnings.empty:
            print(f"  WARNING: {event['ticker']} {event['filing_date']}: "
                  f"no earnings data to compare against; days/timing set to {NOT_FOUND}")
            rows.append(row)
            continue

        gaps = (company_earnings["_date"] - event_date).abs()
        nearest = company_earnings.loc[gaps.idxmin()]        # idxmin returns the first (earlier) of any tie
        days, timing = classify(event_date, nearest["_date"])

        row["earnings_filing_date"] = nearest["filing_date"]
        for column in ["period", "revenue_reported", "eps_diluted", "net_income"]:
            row[column] = nearest[column]
        row["days_to_nearest_earnings"] = days
        row["event_timing"] = timing
        rows.append(row)

    timeline = pd.DataFrame(rows, columns=OUTPUT_COLUMNS)
    if not timeline.empty:
        order = {ticker: position for position, ticker in enumerate(TICKER_ORDER)}
        timeline["_order"] = timeline["ticker"].map(order).fillna(len(order))
        timeline = (timeline.sort_values(["_order", "filing_date"], ascending=[True, False])
                    .drop(columns="_order").reset_index(drop=True))
    return timeline


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------
def describe(row):
    """One readable line for an event in the summary."""
    who = f"{row['person_name']} ({row['title']})"
    if row["event_timing"] == NOT_FOUND:
        return f"    {row['filing_date']}  {row['event_type']:<11} {who}: no earnings date available"
    days, timing = row["days_to_nearest_earnings"], row["event_timing"]
    direction = "before" if row["filing_date"] < row["earnings_filing_date"] else "after"
    when = {
        "before earnings": f"{days} days BEFORE",
        "after earnings": f"{days} days AFTER",
        "same week": ("SAME WEEK, on the same day as" if days == 0 else f"SAME WEEK, {days} days {direction}"),
    }[timing]
    return (f"    {row['filing_date']}  {row['event_type']:<11} {who}: "
            f"{when} the earnings announcement on {row['earnings_filing_date']} ({row['period']})")


def print_summary(timeline, tickers_in_earnings):
    print("\n=== Executive events vs. nearest earnings announcement, by company ===")
    tickers = [t for t in TICKER_ORDER if t in set(tickers_in_earnings) | set(timeline["ticker"])]
    for ticker in tickers + [t for t in timeline["ticker"].unique() if t not in tickers]:
        company_rows = timeline[timeline["ticker"] == ticker]
        print(f"\n{ticker}:")
        if company_rows.empty:
            print("    No executive events in the data")
            continue
        for _, row in company_rows.iterrows():
            print(describe(row))

    counts = timeline["event_timing"].value_counts()
    before = int(counts.get("before earnings", 0))
    after = int(counts.get("after earnings", 0))
    same_week = int(counts.get("same week", 0))
    unknown = int(counts.get(NOT_FOUND, 0))
    print("\n=== Totals across all companies ===")
    print(f"Events BEFORE an earnings announcement (more than {SAME_WEEK_DAYS} days before): {before}")
    print(f"Events AFTER an earnings announcement (more than {SAME_WEEK_DAYS} days after):  {after}")
    print(f"Events in the SAME WEEK as an earnings announcement (within {SAME_WEEK_DAYS} days): {same_week}")
    if unknown:
        print(f"Events with no earnings date to compare: {unknown}")
    print(f"Total events: {len(timeline)}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    earnings = load_csv(EARNINGS_PATH, "earnings_history.csv")
    events = load_csv(EVENTS_PATH, "executive_events.csv")
    print(f"Loaded {len(earnings)} earnings rows and {len(events)} executive events.")

    if events.empty:
        timeline = pd.DataFrame(columns=OUTPUT_COLUMNS)
        timeline.to_csv(OUTPUT_PATH, index=False, encoding="utf-8")
        print("\nexecutive_events.csv has no rows (no Item 5.02 filings in the past 12 months), so there "
              "is nothing to compare against earnings dates.")
        print(f"Saved an empty timeline (header only) to {OUTPUT_PATH}")
        return

    timeline = build_timeline(events, earnings)
    timeline.to_csv(OUTPUT_PATH, index=False, encoding="utf-8")
    print_summary(timeline, earnings["ticker"].tolist())
    print(f"\nSaved {len(timeline)} rows to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
