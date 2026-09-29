"""
hw03_yfinance_check.py

Purpose:     Part 5C cross-validation. Retrieve one company's quarterly revenue
             and net income from Yahoo Finance (yfinance) and compare them with
             the values extracted from the 8-K press release in
             hw03/earnings_history.csv.
Inputs:      hw03/earnings_history.csv
Output:      printed comparison table only (nothing is written to disk)
Author:      Jonah Karst
Generated:   2026-09-29

Run from the command line:
    python hw03/hw03_yfinance_check.py            (defaults to MSFT, its latest 8-K)
    python hw03/hw03_yfinance_check.py MSFT 2026-07-29

The yfinance quarter is chosen by date: it is the quarter that ended shortly
before the 8-K was filed (earnings are filed within about 60 days of period end),
so the two sources are compared for the same quarter.
"""

import csv
import sys
from datetime import date
from pathlib import Path

import yfinance as yf

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

EARNINGS_PATH = Path(__file__).resolve().parent / "earnings_history.csv"
DEFAULT_TICKER = "MSFT"
MAX_DAYS_PERIOD_END_TO_FILING = 75      # an 8-K is filed within this many days after period end
EXACT_TOLERANCE_MILLIONS = 0.5          # rounding to the nearest million
CLOSE_TOLERANCE_PERCENT = 0.5           # "close" = within half a percent


def load_csv_row(ticker, filing_date):
    """Return the earnings_history.csv row for the ticker (latest filing if no date given)."""
    with open(EARNINGS_PATH, encoding="utf-8", newline="") as handle:
        rows = [r for r in csv.DictReader(handle) if r["ticker"] == ticker]
    if not rows:
        sys.exit(f"ERROR: no {ticker} rows in {EARNINGS_PATH}")
    if filing_date:
        rows = [r for r in rows if r["filing_date"] == filing_date]
        if not rows:
            sys.exit(f"ERROR: no {ticker} row filed on {filing_date} in {EARNINGS_PATH}")
    return max(rows, key=lambda r: r["filing_date"])


def pick_row(frame, names):
    """First matching row label in a yfinance statement, or None."""
    for name in names:
        if name in frame.index:
            return name
    return None


def compare(label, csv_value, yahoo_value):
    """Print one comparison line and return the verdict."""
    csv_number = float(csv_value)
    diff = yahoo_value - csv_number
    percent = abs(diff) / csv_number * 100 if csv_number else float("inf")
    if abs(diff) <= EXACT_TOLERANCE_MILLIONS:
        verdict = "MATCH (exact, to the million)"
    elif percent <= CLOSE_TOLERANCE_PERCENT:
        verdict = f"CLOSE (within {CLOSE_TOLERANCE_PERCENT}%)"
    else:
        verdict = "MISMATCH"
    print(f"{label:<12} 8-K text extraction: {csv_number:>12,.1f}   yfinance: {yahoo_value:>12,.1f}   "
          f"diff: {diff:>+10,.1f}  ({percent:.3f}%)  -> {verdict}")
    return verdict


def main():
    ticker = sys.argv[1].upper() if len(sys.argv) > 1 else DEFAULT_TICKER
    filing_date = sys.argv[2] if len(sys.argv) > 2 else None
    row = load_csv_row(ticker, filing_date)
    filed = date.fromisoformat(row["filing_date"])
    print(f"8-K CSV row: {row['ticker']} | filed {row['filing_date']} | {row['period']} | "
          f"revenue {row['revenue_reported']}M | net income {row['net_income']}M\n")

    try:
        statement = yf.Ticker(ticker).quarterly_income_stmt
    except Exception as error:
        sys.exit(f"ERROR: could not download data from Yahoo Finance ({error})")
    if statement is None or statement.empty:
        sys.exit("ERROR: yfinance returned no quarterly income statement data")

    revenue_label = pick_row(statement, ["Total Revenue", "Operating Revenue"])
    income_label = pick_row(statement, ["Net Income", "Net Income Common Stockholders"])
    if not revenue_label or not income_label:
        sys.exit(f"ERROR: expected rows not found in yfinance data. Rows available: {list(statement.index)[:15]}")

    print("Quarters available from yfinance (period end date, in millions of USD):")
    for period_end in sorted(statement.columns, reverse=True):
        print(f"  {period_end.date()}   revenue {statement.loc[revenue_label, period_end] / 1e6:>12,.1f}   "
              f"net income {statement.loc[income_label, period_end] / 1e6:>12,.1f}")

    # The quarter that ended shortly before this 8-K was filed.
    candidates = [c for c in statement.columns if 0 < (filed - c.date()).days <= MAX_DAYS_PERIOD_END_TO_FILING]
    if not candidates:
        sys.exit(f"\nNo yfinance quarter ended within {MAX_DAYS_PERIOD_END_TO_FILING} days before {filed}. "
                 f"Yahoo may not carry that quarter; compare against the list above by hand.")
    period_end = max(candidates)
    print(f"\nComparing the yfinance quarter ended {period_end.date()} with the 8-K filed {filed} "
          f"({(filed - period_end.date()).days} days later):\n")

    yahoo_revenue = statement.loc[revenue_label, period_end] / 1e6
    yahoo_income = statement.loc[income_label, period_end] / 1e6
    compare("Revenue", row["revenue_reported"], yahoo_revenue)
    compare("Net Income", row["net_income"], yahoo_income)


if __name__ == "__main__":
    main()
