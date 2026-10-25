# Wildcat Capital Data Cleaning Report

**To:** Portfolio Committee · **From:** Jonah Karst · **Date:** October 25, 2026
**Scope:** The 8-table warehouse extract (5 dimension, 3 fact tables; 555,401 rows), January 2020 – December 2024

## Executive Summary

The extract is now fit for reporting, with three caveats the committee should know.

The audit found 9 errors and 11 warnings. The most serious ones would have corrupted reporting without
any visible error:

- **Holdings couldn't be linked to securities.** Every one of the 197,175 security references was
  stored in a format (`45.0`) that matches no security record (`45`). Holdings-by-security reporting
  would have returned nothing.
- **25 clients appeared twice**, with altered last names, which inflated the client count.
- **200 transactions ($10.9 million) belonged to client IDs that don't exist.**

All of these are fixed or set aside. On every quality measure, the clean data scores 100% (table
below). Every change is traceable cell by cell (199,228 logged changes), and no row was deleted
without a record: raw rows = clean rows + 225 set-aside rows, proven for every table, in rows and in
dollars.

The three caveats:
1. **Fee revenue should come from the fee table, not the transaction history.** The two disagree by
   $59 million.
2. **Performance figures should exclude 1,475 flagged snapshots.** These are returns outside −90% to
   +100%, mostly from small accounts.
3. **2,410 transactions occur after the client's account closed.** They are kept but flagged.

## Data Quality Before and After

| Table | Rows (raw → clean) | Type validity | Key uniqueness | Rule pass | Referential match |
|---|---|---|---|---|---|
| Transactions | 298,772 → 298,572 | 90.5% → 100% | 100% → 100% | 99.91% → 100% | **81.95% → 100%** |
| Portfolio snapshots | 129,547 → 129,547 | 99.92% → 100% | 100% → 100% | 100% → 100% | 100% → 100% |
| Clients | 2,525 → 2,500 | 100% → 100% | **98.02% → 100%** | 99.61% → 100% | 100% → 100% |
| Advisors | 25 → 25 | 100% → 100% | 100% → 100% | **94.0% → 100%** | n/a |
| Fees, Securities, Dates, Benchmarks | unchanged | 100% | 100% | 100% | 100% (n/a for Dates, Benchmarks) |

Completeness is 100% in every clean table. Blanks that are correct by design, such as no security on
a cash deposit, are not counted as missing.

## What Was Changed

| Issue | Action | Rows |
|---|---|---:|
| Duplicate clients (same person, altered last name, no activity) | Set aside | 25 |
| Transactions for non-existent clients ($10,888,495.37, 0.067% of value) | Set aside | 200 |
| Security IDs stored as `45.0`, which couldn't link to securities | Reformatted | 197,044 |
| Negative share counts on purchases | Sign corrected | 835 |
| Returns stored as text percentages (`9.28%`) | Converted to decimals | 300 |
| Returns in scientific notation | Rewritten, value unchanged | 891 |
| State names spelled out (`Pennsylvania`) | Standardized to codes | 77 |
| Blank client risk profile | Labelled `Unknown` | 75 |
| Advisor certification text `None` | Relabelled `No Certification` | 6 |
| Suspicious but not provably wrong | Flagged, values kept (4,691 flags) | 4,442 |

Every repair was checked against an independent figure before it was accepted:
- **Corrected share counts:** shares × price equals the transaction amount on every purchase.
- **Converted returns:** return − benchmark equals the recorded alpha.
- **Fee amounts:** every fee equals AUM × rate, and its AUM equals the same month's portfolio snapshot.

## Key Judgment Calls

**1. The $1,000 balances were flagged, not corrected.** 420 snapshots show AUM of exactly $1,000.00,
spread across 92 Retail clients, and no account anywhere is below $1,000. That pattern points to a
floor in the source system, not a real balance. The true balance (somewhere from $0 to $1,000) can't
be recovered from any other field, so replacing it would mean making up a number. The rows are
flagged in both the snapshot and fee tables.
*Risk:* small for AUM totals. The larger risk is distorted performance figures (see call 2).

**2. Extreme returns were flagged, not removed.** 1,475 snapshots show year-to-date returns below −90%
(498) or above +100% (977, up to 9,467%). These bounds are a chosen plausibility threshold, not a
hard limit. Only a loss beyond −100% is impossible. They sit well outside anything the benchmarks
produced (−24.0% to +27.4%) and outside the middle 98% of snapshots (−57.4% to +79.4%). The arithmetic in these rows is consistent: return −
benchmark = alpha. They come from small accounts whose deposits and withdrawals are large relative
to their balance, and 981 of them belong to clients who hit the $1,000 floor. The return is not
adjusted for cash flows, so these values aren't errors, but they aren't meaningful performance
either.
*Risk:* any average return that includes them is misleading. Reports must filter on the flag.

**3. Orphan transactions were set aside, not attached to placeholder clients.** 200 transactions
reference client IDs (2702–3192) that exist nowhere in the client table. Creating placeholder clients
would mean inventing their tier, risk profile and AUM.
*Risk:* transaction totals are $10.9M (0.067%) lower. If the clients are real, the source team can
restore the rows unchanged from the set-aside file.

**4. Transactions after account closure were flagged, not deleted.** 131 of 175 inactive clients have
2,410 transactions after their last snapshot. Snapshots and fees both stop, but the transactions keep
going. We can't tell whether the account status or the transactions are wrong: they could be closing
liquidations or misposted entries.
*Risk:* reports that ignore the flag overstate activity for closed accounts.

## Limitations

- **The two fee sources do not reconcile.** Advisory Fee debits in the transaction history total
  $263.7M, while the fee table accrues $204.7M. Only 0.53% of client-quarters agree within 1%, and the
  quarterly-billing explanation was tested and rejected. *Use the fee table for revenue.* It
  reconciles exactly to AUM × rate. Finance should explain the debits.
- **Transaction dates are spread evenly across all seven days.** 28.45% of transactions fall on
  weekends, including 40,630 trades on non-trading days. This is a dating convention in the source, not
  something to correct. Monthly and annual figures are reliable; day-of-week analysis is not.
- **75 clients have no assessed risk profile.** They are labelled `Unknown` and need a suitability
  review. `Unknown` is not a risk category.
- **One fee charged 100.38 bps**, above a 1% level. It is consistent with its own AUM and amount and
  was kept. The overcharge, if any, is $0.34.

---
*AI-assisted report — reviewed for factual accuracy on October 25, 2026 by Jonah Karst*
