# HW6 Measure Library: AUM & Performance

All measures are in the `_Measures` table of `powerbi/hw06.pbix`. Each one uses the DAX pattern for the
additivity class assigned to its column in Assignment 5 Part C:

- **SUM**: additive values (fees, signed cash flows) that can be summed across any dimension.
- **Last balance**: semi-additive balances (`aum`). Take the balance at the last snapshot date in the
  current filter, never a sum across months. Snapshots fall on the 1st of the month, so the date is
  found with `LASTNONBLANK`, not `LASTDATE` or `ENDOFMONTH`.
- **Recompute and weight**: non-additive rates and ratios. Recompute them from additive or last-balance
  parts in every filter context, with a weight where rows differ in size. Never sum or average them.

Figures quoted below come from the pandas side and are reconciled to Power BI in
`reports/measure_reconciliation.csv` (Part B).

## Summary

| # | Measure | Pattern | Format |
|---|---|---|---|
| — | `Total Fees` | SUM | Currency, 2 dp |
| — | `Net Flows` | SUM | Currency, 2 dp |
| 0 | `AUM (naive SUM)` | SUM applied to a balance (**wrong, kept only as a warning**) | Currency, 2 dp |
| 1 | `Ending AUM` | Last balance | Currency, 2 dp |
| 2 | `Ending Clients` | Last balance | Whole number |
| 3 | `Avg AUM per Client` | Recompute (last balance ÷ last balance) | Currency, 2 dp |
| 4 | `Ending AUM LY` | Last balance, shifted one year | Currency, 2 dp |
| 4 | `AUM YoY %` | Recompute | Percentage, 2 dp |
| 5 | `Ending AUM PM` | Last balance, shifted one month | Currency, 2 dp |
| 5 | `AUM MoM %` | Recompute | Percentage, 2 dp |
| 6 | `Avg Monthly AUM` | Recompute and weight (Σ balance ÷ months) | Currency, 2 dp |
| 7 | `Fee Yield (bps)` | Recompute and weight (two fact tables) | Decimal, 2 dp |
| 8 | `Organic Growth Rate` | Recompute (SUM ÷ last balance) | Percentage, 2 dp |
| 9 | `AUM-Weighted Alpha` | Recompute and weight, at the last balance date | Percentage, 2 dp |
| 10 | `Alpha Signal` | Label on a recompute-and-weight measure | Text |
| 11 | `Top 10 Client Share` | Recompute, at the last balance date | Percentage, 2 dp |

---

## Part A: Measure documentation

### Base measures (from ICE 9 and ICE 10)

```DAX
Total Fees = SUM ( fact_fees[amount] )
```
**Pattern:** SUM. Each fee row is one month's charge, so fees add up across clients, advisors and months.
**For a manager:** the revenue Wildcat billed in the period.

```DAX
Net Flows =
CALCULATE ( SUM ( fact_transactions[amount] ), fact_transactions[txn_type] = "Deposit" )
    - CALCULATE ( SUM ( fact_transactions[amount] ), fact_transactions[txn_type] = "Withdrawal" )
```
**Pattern:** SUM. Transaction `amount` is additive only after it is signed by type. Deposits and
withdrawals are both stored as positive amounts, so withdrawals are subtracted.
**For a manager:** new money clients brought in, minus money they took out.

### 0. AUM (naive SUM): wrong, never on a report

```DAX
AUM (naive SUM) = SUM ( fact_portfolio_snapshot[aum] )
```
**Pattern:** SUM applied to a semi-additive balance, which is the mistake this library exists to avoid.
**For a manager:** it adds the same client's balance once per month. With no filter it shows
$566,681,084,542.48, 44.5 times the $12,729,572,078.86 Wildcat actually manages. It is kept only to
show that Power BI and pandas make the same mistake (Part B), and it is not on the Measures page.

### 1. Ending AUM

```DAX
Ending AUM =
CALCULATE (
    SUM ( fact_portfolio_snapshot[aum] ),
    LASTNONBLANK ( dim_date[date], CALCULATE ( COUNTROWS ( fact_portfolio_snapshot ) ) )
)
```
**Pattern:** last balance. `LASTNONBLANK` finds the last date in the filter that has snapshot rows, and
`aum` is summed across clients on that date only.
**For a manager:** how much Wildcat manages at the end of the period: $12,729,572,078.86 on the
December 2024 snapshot.

### 2. Ending Clients

```DAX
Ending Clients =
CALCULATE (
    DISTINCTCOUNT ( fact_portfolio_snapshot[client_id] ),
    LASTNONBLANK ( dim_date[date], CALCULATE ( COUNTROWS ( fact_portfolio_snapshot ) ) )
)
```
**Pattern:** last balance. It is a head count on the same date `Ending AUM` uses, not a count across months.
**For a manager:** how many clients hold an account at the end of the period: 2,325 in December 2024.
That is fewer than the 2,500 in `dim_client`, because clients who left earlier have no final snapshot.

### 3. Avg AUM per Client

```DAX
Avg AUM per Client = DIVIDE ( [Ending AUM], [Ending Clients] )
```
**Pattern:** recompute. A ratio of two last-balance measures, recomputed in every filter context instead
of averaging client rows.
**For a manager:** the typical relationship size at the end of the period, about $5.48M per client in
December 2024. It is the figure to compare across tiers or advisors.

### 4. Ending AUM LY and AUM YoY %

```DAX
Ending AUM LY = CALCULATE ( [Ending AUM], SAMEPERIODLASTYEAR ( dim_date[date] ) )

AUM YoY % = DIVIDE ( [Ending AUM] - [Ending AUM LY], [Ending AUM LY] )
```
**Pattern:** last balance, shifted one year. `LASTNONBLANK` inside `[Ending AUM]` runs on the shifted
dates, so 2024 is compared with the December 2023 snapshot. YoY % is recomputed from the two balances.
`DIVIDE` has no alternate result, so 2020 shows blank, not a misleading 0%.
**For a manager:** how much the book grew in a year from all causes (markets and client flows): 19.58%
in 2024, from $10.64B to $12.73B.

### 5. Ending AUM PM and AUM MoM %

```DAX
Ending AUM PM = CALCULATE ( [Ending AUM], DATEADD ( dim_date[date], -1, MONTH ) )

AUM MoM % = DIVIDE ( [Ending AUM] - [Ending AUM PM], [Ending AUM PM] )
```
**Pattern:** last balance, shifted one month, and a recomputed growth rate.
**For a manager:** short-term momentum: December 2024 ended 4.25% above November ($12.21B to $12.73B).

### 6. Avg Monthly AUM

```DAX
Avg Monthly AUM =
DIVIDE (
    SUM ( fact_portfolio_snapshot[aum] ),
    DISTINCTCOUNT ( fact_portfolio_snapshot[snapshot_date] )
)
```
**Pattern:** recompute and weight. Total balance is divided by the number of distinct snapshot months in
the filter, so every month counts equally whatever the number of clients.
**For a manager:** the balance Wildcat carried on average through the period ($11.29B in 2024). Because
AUM grew during the year, this is below the year-end figure. It is the right base for anything earned
over the whole period, such as fees.

### 7. Fee Yield (bps)

```DAX
Fee Yield (bps) =
DIVIDE ( [Total Fees] * 12 * 10000, SUM ( fact_portfolio_snapshot[aum] ) )
```
**Pattern:** recompute and weight, across two fact tables. Monthly fees are annualized (× 12) and divided
by the sum of monthly balances, so it is weighted by AUM. Both tables are filtered through the shared
`dim_date` and `dim_client`.
**For a manager:** how many basis points per year Wildcat earns on the assets it manages: 43.15 bps in
2024.

### 8. Organic Growth Rate

```DAX
Organic Growth Rate = DIVIDE ( [Net Flows], [Ending AUM LY] )
```
**Pattern:** recompute. Additive flows for the period, divided by the last balance a year earlier.
**For a manager:** growth from client decisions alone, without market moves: net new money equal to 0.73%
of the starting book in 2024. Set against 19.58% total growth, almost all of 2024's growth came from
markets.

### 9. AUM-Weighted Alpha

```DAX
AUM-Weighted Alpha =
VAR LastSnapshot =
    LASTNONBLANK ( dim_date[date], CALCULATE ( COUNTROWS ( fact_portfolio_snapshot ) ) )
RETURN
    CALCULATE (
        DIVIDE (
            SUMX (
                fact_portfolio_snapshot,
                fact_portfolio_snapshot[aum] * fact_portfolio_snapshot[active_alpha_ytd]
            ),
            SUM ( fact_portfolio_snapshot[aum] )
        ),
        LastSnapshot,
        fact_portfolio_snapshot[is_return_suspect] = 0
    )
```
**Pattern:** recompute and weight. `SUMX` weights each account's alpha by its balance, at the last
snapshot only, because `active_alpha_ytd` is year-to-date and only the last month holds the full
period. Suspect returns are removed from both numerator and denominator. The last date is found
before that filter applies, so it is the same date `Ending AUM` uses.
**For a manager:** how far the average managed dollar beat its benchmark: +1.45% for 2024, after
excluding 148 suspect accounts.

### 10. Alpha Signal

```DAX
Alpha Signal =
VAR Alpha = [AUM-Weighted Alpha]
RETURN
    SWITCH (
        TRUE (),
        ISBLANK ( Alpha ), BLANK (),
        Alpha >= 0.02, "Outperforming",
        Alpha <= -0.02, "Lagging",
        "In line"
    )
```
**Pattern:** a text label on a recompute-and-weight measure. The variable evaluates measure 9 once, and
the thresholds are ±0.02 because alpha is stored as a decimal.
**For a manager:** a quick flag for whether a book of business is clearly beating its benchmark (2022;
2024 Retail), clearly lagging, or within 2 points of it.

### 11. Top 10 Client Share

```DAX
Top 10 Client Share =
VAR LastSnapshot =
    LASTNONBLANK ( dim_date[date], CALCULATE ( COUNTROWS ( fact_portfolio_snapshot ) ) )
VAR Top10Clients =
    TOPN (
        10,
        VALUES ( dim_client[client_id] ),
        CALCULATE ( SUM ( fact_portfolio_snapshot[aum] ), LastSnapshot ),
        DESC
    )
RETURN
    DIVIDE (
        CALCULATE ( SUM ( fact_portfolio_snapshot[aum] ), Top10Clients, LastSnapshot ),
        CALCULATE ( SUM ( fact_portfolio_snapshot[aum] ), LastSnapshot )
    )
```
**Pattern:** recompute, at the last balance date. `VALUES ( dim_client[client_id] )` ranks only the
clients in the current filter (for example one tier in 2024), so the share stays between 0 and 100%.
`ALL ( dim_client )` would rank the whole firm. Every client is ranked by its balance on the same last
snapshot. Ranking by `[Ending AUM]` would use each client's own last snapshot, and a client who left
earlier could then rank in the top 10 while adding nothing to the year-end balance.
**For a manager:** concentration risk: the 10 largest clients hold 6.16% of firm AUM. Within UHNW in 2024
it is 8.13%, so losing a few large relationships would hit that tier hardest.

---

## Part C: Design questions

*(Pending.)*
