# Wildcat Capital Data Cleaning Report

**To:** Portfolio Committee · **From:** Jonah Karst · **Date:** October 25, 2026
**Scope:** The 8-table warehouse extract (5 dimension, 3 fact tables; 555,401 rows), January 2020 – December 2024

## Executive Summary

The extract is now fit for reporting on clients, AUM, fees and performance, with four caveats.

The audit found 9 errors and 16 warnings. The most serious ones would have corrupted reporting without
any visible error:

- **Transactions couldn't be linked to securities.** All 197,175 security references were stored as
  `45.0`, which matches no security record (`45`).
- **25 clients appeared twice**, with altered last names.
- **200 transactions ($10.9 million) belonged to client IDs that don't exist.**

All of these are fixed or set aside. Every change is traceable cell by cell (199,228 logged changes),
and nothing was deleted without a record: raw rows = clean rows + 225 set-aside rows, proven for every
table, in rows and in dollars.

The four caveats:
1. **Use the fee table for fee revenue.** The transaction history disagrees with it by $59 million.
2. **Exclude the 1,475 flagged snapshots from performance figures.** These are extreme returns, mostly
   from small accounts.
3. **Don't build holdings from trades.** 72% of Sells exceed the shares the client bought.
4. **2,410 transactions occur after the client's account closed.** They are kept but flagged, since it's
   unclear whether the account status or the transactions are wrong.

## Data Quality Before and After

| Table | Rows (raw → clean) | Type validity | Key uniqueness | Rule pass | Referential match |
|---|---|---|---|---|---|
| Transactions | 298,772 → 298,572 | 90.5% → 100% | 100% → 100% | 99.91% → 100% | **81.95% → 100%** |
| Portfolio snapshots | 129,547 → 129,547 | 99.92% → 100% | 100% → 100% | 100% → 100% | 100% → 100% |
| Clients | 2,525 → 2,500 | 100% → 100% | **98.02% → 100%** | 99.61% → 100% | 100% → 100% |
| Advisors | 25 → 25 | 100% → 100% | 100% → 100% | **94.0% → 100%** | n/a |
| Fees, Securities, Dates, Benchmarks | unchanged | 100% | 100% | 100% | 100% (n/a for Dates, Benchmarks) |

Completeness is 100% in every clean table; blanks that are correct by design, such as no security on a
cash deposit, are not counted as missing. **"100%" means the data passes every rule that could be
enforced.** The limitations below are problems we identified but could not repair without inventing
data.

## What Was Changed

| Issue | Action | Rows |
|---|---|---:|
| Duplicate clients; transactions for non-existent clients | Set aside | 25 + 200 |
| Security IDs stored as `45.0` | Reformatted | 197,044 |
| Negative share counts on purchases | Sign corrected | 835 |
| Returns stored as `9.28%` or in scientific notation | Converted, value unchanged | 300 + 891 |
| State names spelled out; certification text `None` | Standardized | 77 + 6 |
| Blank client risk profile | Labelled `Unknown` | 75 |
| Suspicious but not provably wrong | Flagged, values kept | 4,442 |

Every repair was checked against an independent figure. Corrected share counts satisfy shares × price
= amount, and converted returns satisfy return − benchmark = alpha. Every fee equals AUM × rate, with
AUM equal to the same month's snapshot.

## Key Judgment Calls

**1. The $1,000 balances were flagged, not corrected.** 420 snapshots, across 92 Retail clients, show
AUM of exactly $1,000.00, and no account is ever below it. That points to a floor in the source system.
The true balance ($0 to $1,000) can't be recovered, so replacing it would mean making one up.
*Risk:* negligible for AUM totals; the real effect is on returns (call 2).

**2. Extreme returns were flagged, not removed.** 1,475 snapshots show year-to-date returns below −90%
(498) or above +100% (977, up to 9,467%). These bounds are a chosen plausibility threshold, not a hard
limit, since only a loss beyond −100% is impossible. They sit far outside the benchmarks' range (−24.0%
to +27.4%) and the middle 98% of snapshots (−57.4% to +79.4%). The arithmetic is consistent, but the
return isn't adjusted for cash flows: small accounts with large deposits or withdrawals show them as
gains or losses, and 981 of these rows belong to clients who hit the $1,000 floor.
*Risk:* any average return that includes them is misleading. Reports must filter on the flag.

**3. Orphan transactions were set aside, not given placeholder clients.** 200 transactions reference
client IDs (2702–3192) that exist nowhere. Placeholder clients would need an invented tier, risk
profile and AUM.
*Risk:* transaction totals are $10.9M (0.067%) lower; the rows can be restored unchanged if the
clients turn up.

**4. Trades that don't fit holdings were documented, not altered.** 42,975 of 59,720 Sells (72%) sell
more shares than the client bought, just as often for clients who joined after 2020, so older
holdings don't explain it. 13.2% of dividends are on securities never bought. With no holdings table,
there is nothing to correct against.
*Risk:* position, average-cost and yield reports are unreliable. Account value should come from
snapshot AUM.

## Limitations

- **The two fee sources do not reconcile.** Advisory Fee debits total $263.7M against $204.7M in the
  fee table. Only 0.53% of client-quarters agree within 1%, and quarterly billing was tested and
  rejected. Finance should explain the debits.
- **Trade prices aren't a market series.** 25.3% of trades are priced below half or above double their
  security's median price. Cash amounts are reliable; price analysis is not.
- **Dates and calendar.** 28.45% of transactions fall on weekends, and 44,241 trades fall on
  weekends or market holidays. The date table also marks all 47 market holidays as trading days. Monthly and
  annual figures are reliable; day-level trading analysis is not.
- **75 clients have no assessed risk profile** (`Unknown`) and need a suitability review. Zip codes
  don't match the client's state for about 90% of clients, so geography should use state.

---
*AI-assisted report — reviewed for factual accuracy on October 25, 2026 by Jonah Karst*
