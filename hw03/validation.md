# HW3 Validation

Company used for the known-answer checks: **Microsoft (MSFT)**.

## 5A: Known-Answer Check: Earnings

**Quarter checked:** Microsoft fiscal Q4 2026 (quarter ended June 30, 2026), 8-K filed 2026-07-29.

**Official source:** Microsoft Investor Relations earnings page (Q4 FY26 results), which reports total revenue of **$90,007 million** and diluted EPS of **$4.81**. I also confirmed both figures independently in the same release as filed with the SEC (Exhibit 99.1 to the 8-K, `msft-ex99_1.htm`): the income statement lists "Total revenue 90,007" (in millions) and "Diluted Earnings per Share $4.81" (GAAP).

`revenue_reported` is stored in millions of USD. The CSV row in `hw03/earnings_history.csv` after the fix described below:
`Microsoft Corporation,MSFT,0000789019,2026-07-29,fourth quarter fiscal 2026,90007.0,4.81,35766.0`

| Check | Official Source | Your CSV | Match? |
|---|---|---|---|
| Microsoft Q4 FY26 Revenue | $90,007 million | 90007.0 | Yes, exact (after the fix below; it was 90000.0 on the first run) |
| Microsoft Q4 FY26 EPS Diluted | $4.81 | 4.81 | Yes, exact |

### Discrepancy found and fixed (before and after)

**Before (first run).** Revenue came back as `90000.0` against the official `90,007`, a $7 million (0.008%) gap. The pipeline had matched the press release's prose sentence ("Revenue was **$90.0 billion** and increased 18%"), which is rounded to one decimal place, and converted it to 90,000 million. The exact figure, 90,007, is in the income-statement table of the same document, but the script only looked at the table when the prose sentence was missing. The period, the units, and the choice of total quarterly revenue (not a segment or year-to-date figure) were all correct, so this was a precision problem, not a wrong-number problem.

**The fix.** Following the assignment's process for a mismatch, I revised the extraction. The prose pattern is unchanged; what changed is that after finding a prose figure the script now looks for a revenue row in the release's income-statement table and, if one agrees with the prose figure *within the prose's own rounding*, uses that exact table figure instead. "$90.0 billion" is only precise to $0.1 billion, so any table value within +/- $50 million qualifies (90,007 does). If no table value agrees, the prose figure is kept, so the fix cannot pull in a year-to-date or segment number.

| | Before | After |
|---|---|---|
| Revenue pattern | `REVENUE_NARRATIVE` only: `(?:revenues?\|net sales) (?:of\|was\|were\|...) \$(number) (billion\|million)` -> 90.0 billion -> 90,000 | Same prose pattern, plus `REVENUE_TABLE_ROW`: `(?:total )?(?:net )?(?:revenues?\|net sales) \$?(\d{1,3}(?:,\d{3})+)` accepted only if within the prose figure's rounding tolerance -> "Total revenue 90,007" -> 90,007 |
| MSFT Q4 FY26 revenue | 90000.0 | 90007.0 (matches official) |

The same change is applied to net income (MSFT Q4 went from 35,800 to 35,766, which matches "Net Income $35,766" in the release's table).

**Did it resolve the discrepancy?** Yes. After rerunning, MSFT Q4 revenue is 90007.0, exactly matching the official figure.

**Effect across the whole dataset.** I tested the change on all 20 filings before rerunning. 18 values changed (16 revenue values across Apple, Microsoft, NVIDIA and Walmart, plus two Microsoft net income values; every other value was unchanged), and every one moved by less than 0.1% of its old value (largest: $49 million on Walmart's roughly $177.8 billion quarter). None of the changes were large, which is what the tolerance rule is designed to guarantee. `NOT_FOUND` count stayed at 0. JPMorgan's revenue and net income are not affected and remain rounded to $0.1 billion (for example 57,300), because JPMorgan's main press release has no income-statement table; its detailed tables are in a separate supplement exhibit that the script does not read once the prose figure is found. That is a known remaining precision limit, not a mismatch I found against an official figure.

## 5B: Known-Answer Check: Executive Events

**Event checked:** Carmine Di Sibio's appointment to the Microsoft board (row from `hw03/executive_events.csv`):
`Microsoft Corporation,MSFT,0000789019,2026-05-14,appointment,Carmine Di Sibio,Director,2026-05-13`

**Public source:** Microsoft's own news release, "Microsoft announces appointment of Carmine Di Sibio to board of directors," dated May 14, 2026:
https://news.microsoft.com/source/2026/05/14/microsoft-announces-appointment-of-carmine-di-sibio-to-board-of-directors/
(The same release is Exhibit 99.1 to the 8-K filed on 2026-05-14, which I read to confirm the wording.)

| Check | News Source Confirms? | Notes |
|---|---|---|
| Person name and title | Yes | The release announces "the appointment of Carmine Di Sibio, former global chairman and CEO of EY, to the Microsoft board of directors." Name matches exactly, and a board seat matches the CSV title `Director`. |
| Event type (departure/appointment) | Yes | It is an appointment, matching `appointment`. There is no departure in this filing; the board grew to 13 members. |
| Effective date | Partly | The release is dated May 14, 2026, which matches the CSV `filing_date`, but it does not state an effective date. The CSV's `2026-05-13` comes from the 8-K text ("effective May 13, 2026"), one day before the public announcement. The two are consistent, not contradictory: May 14 is the announcement date and May 13 is when the board appointment took effect. |

## 5C: Cross-Validation: Earnings via Yahoo Finance

**Company and quarter:** Microsoft fiscal Q4 2026 (quarter ended June 30, 2026), the same quarter checked in 5A.

**Method:** `hw03/hw03_yfinance_check.py` (a small script using `yfinance`, prompted as "Write Python using yfinance to get the most recent quarterly revenue and net income for MSFT," then extended to select the quarter by date so both sources cover the same quarter). It reads the MSFT row from `earnings_history.csv`, pulls Yahoo's quarterly income statement, and compares the yfinance quarter that ended 29 days before the 8-K filing date (2026-06-30).

| Metric | From 8-K text extraction | From yfinance | Match? |
|---|---|---|---|
| Revenue | $90,007 million | $90,007 million | Yes, exact (0.000% difference) |
| Net Income | $35,766 million | $35,766 million | Yes, exact (0.000% difference) |

No disagreement to explain. Because the check is cheap, I also compared the other quarters that yfinance carries for Microsoft against the CSV, and every one matches exactly:

| Quarter ended | CSV revenue / net income (8-K text) | yfinance revenue / net income |
|---|---|---|
| 2026-03-31 | 82,886 / 31,778 | 82,886 / 31,778 |
| 2025-12-31 | 81,273 / 38,458 | 81,273 / 38,458 |
| 2025-09-30 | 77,673 / 27,747 | 77,673 / 27,747 |

(A fifth yfinance quarter, ended 2025-06-30 with revenue 76,441 and net income 27,233, has no CSV row because it is older than our four most recent 8-Ks. The 76,441 figure does match the prior-year column of the Q4 FY26 release.)

**What this does and does not show.** The two sources are independent in how the numbers were retrieved (regex over an SEC press release versus Yahoo Finance's data feed), so exact agreement supports both the extraction and the 5A fix. Both trace back to the figures Microsoft reported, so this confirms the pipeline read the right numbers; it does not audit the reported figures themselves. The check covers only Microsoft's revenue and net income. It does not validate the other four companies, and it does not cover diluted EPS, which is checked against the official source only in 5A.

## 5D: Pipeline Integrity Checks

| Check | Expected | Actual | Pass/Fail |
|---|---|---|---|
| `earnings_history.csv` row count | Up to 20 (5 companies x 4 quarters) | 20 (4 per company: AAPL, MSFT, NVDA, JPM, WMT) | Pass |
| `executive_events.csv` row count | At least 0 (document actual) | 30 events from 19 Item 5.02 filings (3 filings skipped as compensation-only: MSFT 2025-12-08, NVDA 2026-03-06, JPM 2026-01-22) | Pass |
| `corporate_events_timeline.csv` created | Yes | Yes, 30 rows (one per executive event) with `days_to_nearest_earnings` and `event_timing` | Pass |
| Rows with all three fields `"NOT_FOUND"` | 0 (investigate if > 0) | 0. No earnings row contains any `NOT_FOUND` | Pass |

Additional observation, outside the four required checks: the executive events file has 3 rows with `effective_date` = `NOT_FOUND` (Reid Hoffman and Carlos Rodriguez at Microsoft, Marianne Lake at JPMorgan). These were investigated: each filing describes a departure without stating any effective date (the two directors are not standing for re-election at a future annual meeting, and Lake is retiring), so `NOT_FOUND` is the correct value, not an extraction failure. No executive row has a `NOT_FOUND` name or title.
