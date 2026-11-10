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
| 2 | `Ending Clients` | Last balance | Number with thousands separator (`#,0.00`) |
| 2 | `Ending Clients Display` | Text label on a last-balance measure (card only) | Text (`#,##0` via FORMAT) |
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

```DAX
Ending Clients Display = FORMAT ( [Ending Clients], "#,##0" )
```
**Pattern:** a text label on the last-balance measure above. It is for display only, on the Ending
Clients card.
**Why it exists:** Power BI's new card visual kept auto-scaling `Ending Clients` to "2K", even with
display units set to None, and no setting fixed it (README, Power BI Model). `FORMAT` turns the number
into text ("2,325"), which a card can't rescale.
**Limits:**
- **It is text,** so it can't be summed, sorted numerically or used in another measure. Every
  calculation uses `Ending Clients`.
- **Blank context:** where there's no snapshot, `FORMAT` returns an empty string, not BLANK.

**For a manager:** the same head count as `Ending Clients`, shown in full on the card.

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

Every figure below is computed and pinned by `scripts/02_design_questions.py` (79 figures). The script
fails if one changes, and writes `reports/design_questions.csv` only when all are confirmed. Figures
taken from the Part A measures (such as Fee Yield by tier) are reconciled in
`reports/measure_reconciliation.csv` instead.

### (a) Ending AUM vs SUMX over clients

| With no filters | Value |
|---|---:|
| `Ending AUM` | $12,729,572,078.86 |
| `SUMX ( VALUES ( dim_client[client_id] ), [Ending AUM] )` | $13,149,297,713.80 |
| Difference | **$419,725,634.94** |

I ran both in Power BI's DAX query view and recomputed them in pandas; the results are identical.

`Ending AUM` evaluates `LASTNONBLANK` once, for the whole firm. It finds December 2024 and adds up the
2,325 accounts on that snapshot. The SUMX evaluates `[Ending AUM]` once per client instead. Context
transition filters to that client, so `LASTNONBLANK` finds **that client's own** last snapshot. For
the 175 clients who left the firm (13 in 2022, 162 in 2023, all `is_active = False` in `dim_client`),
that is a balance from 2022 or 2023. Their last recorded balances add up to $419,725,634.94, which is
exactly the difference. The SUMX adds balances from different dates, including money that left Wildcat
more than a year ago.

**"How much do we manage today?" is answered by `Ending AUM`: $12.73B.** The SUMX overstates it by
3.3%. A per-client SUMX belongs only in a question like "what was each client worth when we last saw
them?", never in a firm total.

### (b) Why Fee Yield (bps) is below the ICE 9 Effective Fee Rate in 2024

| 2024 | Formula | bps |
|---|---|---:|
| `Fee Yield (bps)` | 2024 fees × 12 × 10,000 ÷ Σ snapshot `aum` | 43.15 |
| ICE 9 `Effective Fee Rate (bps)` | 2024 fees × 12 × 10,000 ÷ Σ fee `aum_basis` | 45.53 |

Both use the same numerator, so the gap is in the denominators. The pandas evidence:

1. On every month that has a fee row, `aum_basis` equals the snapshot's `aum` (100% of 26,216 matched
   months). The two measures don't disagree about balances.
2. **1,684 of the 27,900 snapshot months in 2024 (6.0%) have no fee row at all.** Those months hold 5.22%
   of 2024's summed AUM. `Fee Yield` counts their AUM in its denominator; `Effective Fee Rate` never
   sees them.
3. If `Fee Yield`'s denominator is limited to the months that do have a fee, it becomes 45.53 bps,
   **exactly** the Effective Fee Rate. The whole 2.38 bps gap is those unbilled months:
   45.53 × (1 − 0.0522) = 43.15.

**The data limitation:** `fact_fees` has no row for 7,350 of the 129,547 account-months (all years). There
are no zero-amount fee rows, so the data cannot tell a **waived** fee (a month that was genuinely free)
from a fee that was **charged but never recorded**. The gap isn't a policy pattern that would explain it:
- **Coverage:** the missing months appear in every tier, account type, risk profile and year, at 3.3% to
  6.0% of each year's AUM.
- **Onboarding:** a client's onboarding month (the month of `client_since`) is unbilled a little more
  often than other months (72 of 968, or 7.4%, against 5.7% overall). But those 72 are only 1% of the
  7,350 unbilled months, so onboarding waivers do not explain the gap.
- **Transactions:** `fact_transactions` can't settle it either. An Advisory Fee debit appears in 23.0% of
  unbilled months and 23.5% of billed months, the same rate.

So Effective Fee Rate is the **price charged on billed assets**, and Fee Yield is the **revenue earned on
all managed assets**. The 2.38 bps between them is revenue Wildcat either waived or failed to record.
That should be resolved with the billing system before either number is used to forecast revenue.

### (c) Why AUM-Weighted Alpha uses the last snapshot only and excludes suspect returns

**Last snapshot only.** `active_alpha_ytd` is **year-to-date**. It resets each January and accumulates, so
each month already includes every earlier month. In 2024 the AUM-weighted alpha by month rises from
−0.01% in January to 1.45% in December. Only the last snapshot holds the full period:
- **Averaging** the 12 monthly values gives 0.30%, understating the year almost 5 times (4.86).
- **Summing** them would count January's alpha 12 times.

A side effect to keep in mind: with no filter, or a multi-year filter, the last snapshot is December
2024. The measure then shows **2024's** alpha, not alpha since 2020.

**Excluding `is_return_suspect = 1`.** The flagged returns are data errors, not performance:
- **Size:** at the December 2024 snapshot there are 148 of them, with alphas up to 7,133.8% (71.34) and a
  median of 53.6%. Every unflagged alpha is within ±49.8%.
- **Who:** all 3,875 flagged rows in the data belong to Retail clients.
- **Impact:** they hold little money, so they move the firm-wide figure only slightly. In Retail they
  triple it.

| December 2024 snapshot | Firm | Retail |
|---|---:|---:|
| **AUM-weighted, suspects excluded (the measure)** | **1.45%** | **2.40%** |
| Simple mean of `active_alpha_ytd`, same rows | 0.88% | — |
| AUM-weighted, suspects **included** | 1.67% | 7.62% |
| Simple mean, suspects included | 15.56% | — |

The simple mean (0.88%) is below the weighted figure (1.45%), so larger accounts outperformed smaller
ones. Weighting answers the question a manager asks: how did the average **managed dollar** do against
its benchmark? Including suspects, a simple mean would claim 15.6% alpha for the firm. The weighted
version is protected only because the suspect accounts are small; in Retail it still jumps from 2.40% to
7.62%. Neither Alpha Signal changes here (the firm stays "In line", Retail stays "Outperforming"), but
the Retail figure would be wrong by a factor of three.

### (d) Organic Growth Rate by client tier, 2024

| 2024 | Organic Growth Rate | AUM YoY % | Growth not from flows | Net flows | Deposits ÷ start | Withdrawals ÷ start |
|---|---:|---:|---:|---:|---:|---:|
| HNW | 1.18% | 19.64% | 18.46% | $25.2M | 5.6% | 4.4% |
| Retail | **9.87%** | 19.13% | 9.26% | **$44.2M** | 54.8% | 44.9% |
| UHNW | 0.10% | 19.59% | 19.49% | $8.1M | 0.6% | 0.5% |

"Growth not from flows" = AUM YoY % − Organic Growth Rate: market returns and everything else that
isn't a deposit or withdrawal.

**What it says.** Wildcat's **net new money comes from Retail**. Retail added 9.87% of its starting book,
$44.2M, which is more than half of the firm's $77.5M in 2024 net flows, from the tier holding about 4% of
AUM. UHNW, the largest book, added almost nothing (0.10%, $8.1M). Total growth is nearly the same in every
tier (19.1% to 19.6%), so for HNW and UHNW almost all of 2024's growth (18.5 and 19.5 points) came from
something other than client money: mostly markets. Retail is the only tier where client flows drove about
half the growth.

**What it does not tell you.**
- **Why AUM grew.** "Growth not from flows" mixes market returns, fee debits and anything else. Organic
  Growth Rate can't explain why Retail's non-flow growth (9.3%) was half that of HNW and UHNW (about 19%).
- **How much money moved.** Retail clients deposited 54.8% and withdrew 44.9% of their starting balance
  during 2024. A net 9.9% hides very heavy gross churn. In HNW and UHNW, gross flows were small.
- **Whether clients were won or lost.** No client joined or left any tier in 2024 (0 gained, 0 lost; all
  175 departures were in 2022–23). Every dollar of 2024 flow came from existing clients. Organic Growth
  Rate would score a new client and a top-up from an old one the same way.
- **What the growth is worth.** Retail pays 82.81 bps against UHNW's 36.14 bps (`Fee Yield`, Part A), so
  a dollar of Retail flow earns more than twice as much. Organic Growth Rate counts dollars, not revenue.
- **Scale.** Retail's starting book ($448M) is small, so a modest dollar amount produces a large ratio.
  For "where does our growth come from", compare net flows in **dollars**, alongside the rate.
