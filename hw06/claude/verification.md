# Verification: Claude's `AUM-Weighted Alpha` (measure 9)

Claude's draft (`dax_session.md`) finds the last snapshot with `MAX ( fact_portfolio_snapshot[snapshot_date] )`
and weights a `CALCULATETABLE` of that date's non-suspect rows. My Part A measure uses
`LASTNONBLANK ( dim_date[date], … )` inside `CALCULATE`. The two are written differently and should
give identical results. All tests ran against the open `hw06.pbix` model, and against pandas.

## Did it run as written? What did the test query return?

**Yes.** Claude's test query ran unchanged in DAX query view, with no errors, and returned four result
sets:

| Test | Result |
|---|---|
| A. Grand total | last snapshot 2024-12-01; 2,325 rows on it, 2,177 weighted; alpha **0.0144799** |
| B. By year | every year resolves to its December 1 snapshot; alpha −0.0068, −0.0016, **0.0285**, 0.0177, 0.0145 for 2020–2024 |
| C. 2024 by tier | HNW 687 of 687 rows weighted, 0.0140; **Retail 1,246 of 1,394**, 0.0240; UHNW 244 of 244, 0.0141 |
| D. Suspect-last clients | clients 29, 39, 76, 81, 93: alpha BLANK |

## Which rows of `measure_reconciliation.csv` prove it

The 9 `AUM-Weighted Alpha` rows: `total`, `year=2020` … `year=2024`, and `year=2024|client_tier=` HNW,
Retail and UHNW. Every value in A–C above equals the Power BI value in those rows to all 15 digits (e.g.,
`total` 0.0144799468005643). Those rows match the independent pandas calculation within 5.2e-17, so
Claude's measure is proven against pandas too. The 9 `Alpha Signal` rows match as well, since that
measure reads its alpha from the same calculation.

## Edge cases checked

1. **Grand total.** The only date is 2024-12-01. It weights 2,177 = 2,325 − 148 suspect accounts, and the
   148 matches pandas. The result is 2024 year-to-date alpha, not alpha since 2020, as Claude warned.
2. **`dim_date[year]` = 2022.** This is the only year above the +2% threshold: 2.85%, so "Outperforming".
   The draft gives the same value as the Part A measure and pandas, so the label is right.
3. **2024 tier table.** All 148 Dec 2024 suspects are Retail (1,394 → 1,246 rows). HNW and UHNW lose
   none. The Total row is the firm's 1.45%, not a sum of tiers.
4. **A context where every last-date row is suspect.** In 160 clients (pandas finds the same 160), the
   client's own last snapshot is suspect. Both measures return BLANK for all 160. Client 81 shows why
   this matters: its last clean snapshot (November 2024, −8.87%) was not used as a fallback.
5. **Every other context.** Draft vs Part A compared in 14,046 contexts:

   | Grid | Contexts | Alpha differs | Date differs |
   |---|---:|---:|---:|
   | client × year | 11,316 | 0 | 0 |
   | year × month | 60 | 0 | 0 |
   | advisor × year | 125 | 0 | 0 |
   | benchmark × tier × year | 45 | 0 | 0 |
   | client, all time | 2,500 | 0 | 0 |

## What I changed, and why

**The measure: nothing.** It returned the right value in every context tested, so no change was needed.
I kept the Part A version in `_Measures`, because the results are identical and a second copy would only
be a duplicate on the report.

**The test query had two flaws:**
- **D's filter only worked by accident.** It keeps clients with `[Rows weighted] = 0`, but
  `COUNTROWS` of an empty table returns BLANK, not 0. The filter worked only because DAX treats
  `BLANK = 0` as true. `ISBLANK ( [Rows weighted] )` says what is meant.
- **D's output was unsorted.** It has no `ORDER BY`, so the five clients came back unsorted (93, 81, 39,
  29, 76). They are the right five, the lowest client IDs per pandas. `ORDER BY dim_client[client_id]`
  would fix the order.

## A claim I confirmed

**Claim 1:** "`MAX ( fact_portfolio_snapshot[snapshot_date] )` finds the same date as `LASTNONBLANK`
in every filter context here."
- **Confirmed in Power BI:** the two dates were equal in all 14,046 contexts above.
- **Confirmed in pandas:** the reason holds, because every snapshot date exists in `dim_date`.

**Claim 3**, BLANK instead of a fallback to an earlier month, was also confirmed (edge case 4).

**Claim 5** ("doesn't rely on `dim_date` being marked as a date table") is true by inspection: there are
no time-intelligence functions. I didn't test it, because unmarking the date table would break the
LY/PM measures in the model.
