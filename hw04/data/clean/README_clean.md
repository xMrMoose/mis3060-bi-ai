# Wildcat Capital — Clean Data Set

Produced by [`scripts/02_clean.py`](../../scripts/02_clean.py) from the raw extract in `data/dirty/`.
Each change is justified in [`decision_log.md`](../../decision_log.md) (D-xx IDs below) and traced
cell by cell in [`data/audit/value_changes.csv`](../audit/value_changes.csv).

| File | Raw rows | Clean rows | Quarantined | Added flag columns |
|---|---:|---:|---:|---|
| `dim_advisor.csv` | 25 | 25 | 0 | — |
| `dim_benchmark.csv` | 8 | 8 | 0 | — |
| `dim_client.csv` | 2,525 | 2,500 | 25 | — |
| `dim_date.csv` | 1,827 | 1,827 | 0 | — |
| `dim_security.csv` | 500 | 500 | 0 | — |
| `fact_fees.csv` | 122,197 | 122,197 | 0 | `flag_aum_floor` |
| `fact_portfolio_snapshot.csv` | 129,547 | 129,547 | 0 | `flag_aum_floor`, `flag_return_outlier` |
| `fact_transactions.csv` | 298,772 | 298,572 | 200 | `flag_after_last_snapshot` |

Quarantined rows are in `data/audit/quarantine_dim_client_duplicates.csv` and
`data/audit/quarantine_fact_transactions_orphan_client.csv`. They hold the rows exactly as received (no
cleaning step touches them; `02_clean.py` verifies this) plus a `quarantine_reason` column, and
`duplicate_of_client_id` for clients.

## Relationships

All are many-to-one from the fact/child table to the dimension, single-direction filtering.

| # | From (many) | To (one) | Notes |
|---|---|---|---|
| 1 | `fact_fees.client_id` | `dim_client.client_id` | 100% match |
| 2 | `fact_fees.advisor_id` | `dim_advisor.advisor_id` | 100% match |
| 3 | `fact_portfolio_snapshot.client_id` | `dim_client.client_id` | 100% match |
| 4 | `fact_portfolio_snapshot.advisor_id` | `dim_advisor.advisor_id` | 100% match |
| 5 | `fact_portfolio_snapshot.benchmark_id` | `dim_benchmark.benchmark_id` | 100% match |
| 6 | `fact_transactions.client_id` | `dim_client.client_id` | 100% match after D-07 |
| 7 | `fact_transactions.advisor_id` | `dim_advisor.advisor_id` | 100% match |
| 8 | `fact_transactions.security_id` | `dim_security.security_id` | 100% of non-blank keys after D-05; **blank on 101,597 cash rows by design** (D-10) |
| 9 | `dim_client.advisor_id` | `dim_advisor.advisor_id` | Snowflake; fact advisor always equals the client's advisor |
| 10 | `dim_security.benchmark_id` | `dim_benchmark.benchmark_id` | Snowflake |
| 11 | `fact_fees.fee_date` | `dim_date.date` | Monthly, always the 1st |
| 12 | `fact_portfolio_snapshot.snapshot_date` | `dim_date.date` | Monthly, always the 1st |
| 13 | `fact_transactions.txn_date` | `dim_date.date` | Daily |

- Join facts to `dim_date` on **`date`**, not `date_id`. No fact table carries `date_id`.
- **Do not** relate `dim_client.client_since` to `dim_date`. 1,549 clients started before 2020, and the
  calendar covers 2020–2024 only (D-18).

## Column types for a BI tool

Read every file as text first, then set these types explicitly. **Do not let the tool auto-detect.**

| Type | Columns |
|---|---|
| **Text, must stay text** | `dim_client.zip_code` (leading zeros, e.g. `03897`); `dim_client.primary_account_type` and `fact_portfolio_snapshot.account_type` (`529` is a plan name, not a number); `dim_security.ticker`; `dim_benchmark.ticker_proxy` |
| **Whole number** | all `*_id` columns; `dim_client.age`; `dim_advisor.years_experience`, `aum_target_mm`; `dim_date.year`, `quarter`, `month`, `week_of_year`; `fact_portfolio_snapshot.year`, `month` |
| **Date (YYYY-MM-DD)** | `dim_date.date`, `dim_client.client_since`, `fact_fees.fee_date`, `fact_portfolio_snapshot.snapshot_date`, `fact_transactions.txn_date` |
| **Decimal / currency** | `initial_aum`, `aum`, `aum_basis`, `amount`, `price`, `shares` (4 dp), `bps_charged`, `expense_ratio_bps` |
| **Decimal fraction, format as %** | `return_ytd`, `benchmark_return_ytd`, `active_alpha_ytd`, `cash_pct` (0.0928 = 9.28%) |
| **True/False** | `dim_client.is_active`, `dim_security.is_etf` (stored `True`/`False`); `dim_date.is_month_end`, `is_quarter_end`, `is_year_end`, `is_trading_day` (stored `0`/`1`) |
| **Whole number 0/1** | every `flag_*` column |

Blank cells are real nulls: `security_id` / `shares` / `price` on cash transactions, `sector` on ETFs,
`expense_ratio_bps` on non-ETFs. They are not zeros.

## Flag columns added

A flag marks a row that is suspicious but can't be corrected without inventing data. Values are
kept unchanged; `1` = flagged, `0` = not flagged. Nothing is excluded by default; filter on the flag.

| Column | Table(s) | Rows = 1 | Meaning |
|---|---|---:|---|
| `flag_after_last_snapshot` | fact_transactions | 2,410 | Client is inactive and the transaction falls after the month of its last snapshot (131 clients). Snapshots and fees say the account closed; these transactions say otherwise (D-08). |
| `flag_aum_floor` | fact_portfolio_snapshot, fact_fees | 420 / 386 | AUM is exactly $1,000.00, the source system's floor. True AUM is between $0 and $1,000 and can't be recovered. Every flagged fee sits on a flagged snapshot for the same client-month (D-13). |
| `flag_return_outlier` | fact_portfolio_snapshot | 1,475 | `return_ytd` is below −90% (498) or above +100% (977). Values are internally consistent (return − benchmark = alpha) but not cash-flow-adjusted; 981 belong to clients that hit the AUM floor (D-14). |

## Changes made to values

| Decision | Table.column | Change | Rows |
|---|---|---|---:|
| D-05 | fact_transactions.security_id | `45.0` → `45` | 197,044 |
| D-11 | fact_portfolio_snapshot.return_ytd | `9.28%` → `0.0928` | 300 |
| D-12 | fact_portfolio_snapshot.return_ytd / active_alpha_ytd | `-1.9e-05` → `-0.000019` | 135 / 756 |
| D-02 | dim_client.state | `Pennsylvania` → `PA` (7 states) | 77 |
| D-04 | dim_advisor.certifications | `None` → `No Certification` | 6 |
| D-06 | fact_transactions.shares | negative Buy shares → absolute value | 835 |
| D-03 | dim_client.risk_profile | blank → `Unknown` | 75 |

## Known limitations (not fixed, with reason)

1. **Transaction dates fall on weekends.** 28.45% of transactions are dated on weekends, matching a
   uniform spread across all 7 days. 44,241 Buy/Sell trades fall on non-trading days: 40,630 on
   weekends and 3,611 on market holidays. This looks like a booking-date
   convention, and moving dates would invent them. Day-of-week and trading-day analysis is unreliable;
   monthly and yearly totals are fine (D-09).
2. **AUM at the $1,000 floor is not the true balance.** It can't be recovered from any column. The amount
   is immaterial in totals; exclude flagged rows from performance analysis (D-13).
3. **Returns aren't adjusted for deposits and withdrawals.** Small accounts with large flows show
   returns outside ±100%. Recomputing would need a different method and data not in the extract. Use
   `flag_return_outlier` (D-14).
4. **`risk_profile = Unknown` for 75 clients.** It's a gap to close with a suitability review, not a
   sixth risk category (D-03).
5. **Activity after account closure.** 2,410 transactions are kept but flagged, because it's unclear
   whether `is_active` or the transactions are wrong (D-08).
6. **Advisory Fee transactions don't reconcile to `fact_fees` at any grain.** Debits total $263.7M against
   $204.7M accrued, and only 0.53% of client-quarters agree within 1% (0.11% against Advisory fees
   only). Quarterly billing was tested and rejected. Use `fact_fees` for fee revenue: it reconciles
   exactly to AUM × bps. Treat Advisory Fee transactions as cash movements only (D-20).
7. **One fee at 100.38 bps.** It reconciles to its own amount and was kept (D-15).
8. **$10.9M of transactions (0.067%) are excluded** because their client_ids exist nowhere. They're held in
   quarantine until the source system can supply the clients (D-07).
9. **Benchmark 6 (MSCI Emerging Markets) has no references.** It was kept as a valid dimension member
   (D-17).
10. **Trades aren't linked to holdings.** 42,975 of 59,720 Sells (72.0%) sell more shares than the
    client had bought. This happens just as often for clients who joined after 2020, so pre-extract
    holdings don't explain it. 7,090 of 53,826 dividends (13.2%) are on securities the client never
    bought. **Don't build position or holdings reports from Buys minus Sells**; use
    `fact_portfolio_snapshot.aum` for account value (D-21, D-22).
11. **Trade prices aren't a market price series.** 36,294 of 143,218 trades (25.3%) are priced below half
    or above double their security's median price. Cash amounts reconcile (shares × price = amount),
    but average cost, unrealised gain and price trends are meaningless (D-24).
12. **`is_trading_day` means "weekday".** All 47 weekday NYSE holidays in 2020–2024 are marked as
    trading days (D-23).
13. **Zip codes don't match states** for about 90% of clients. Use `state` for geography, not
    `zip_code` (D-25).
14. **Shared security names.** 3 names belong to two securities each, with different tickers and
    attributes. Report on `ticker`, not `name` (D-26).
