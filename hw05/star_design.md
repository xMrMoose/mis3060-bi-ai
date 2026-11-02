# Wildcat Capital Star Schema Design

MIS3060 HW5 — Jonah Karst

## Part A — Keys

| Table | Type | Primary key | Foreign keys (column → table[column]) |
|---|---|---|---|
| dim_advisor | Dimension | `advisor_id` | — |
| dim_benchmark | Dimension | `benchmark_id` | — |
| dim_client | Dimension | `client_id` | `advisor_id` → dim_advisor[advisor_id] |
| dim_date | Dimension | `date_id` | — |
| dim_security | Dimension | `security_id` | `benchmark_id` → dim_benchmark[benchmark_id] |
| fact_fees | Fact | `fee_id` | `client_id` → dim_client[client_id]<br>`advisor_id` → dim_advisor[advisor_id]<br>`fee_date` → dim_date[date] |
| fact_portfolio_snapshot | Fact | `snapshot_id` | `client_id` → dim_client[client_id]<br>`advisor_id` → dim_advisor[advisor_id]<br>`benchmark_id` → dim_benchmark[benchmark_id]<br>`snapshot_date` → dim_date[date] |
| fact_transactions | Fact | `txn_id` | `client_id` → dim_client[client_id]<br>`advisor_id` → dim_advisor[advisor_id]<br>`security_id` → dim_security[security_id] *(blank on cash rows, see below)*<br>`txn_date` → dim_date[date] |

**How the keys were proven.** `scripts/01_keys.py` checks every key in the table above and stops with an error if one fails. Detail is in `reports/keys_pk.csv` and `reports/keys_fk.csv`.

- **Primary keys:** all 8 are non-blank, unique and whole numbers (0 blanks, 0 duplicates in every table).
- **Foreign keys:** all 13 match their target 100%, with 0 orphan rows. That covers 11 in the fact tables and 2 between dimensions: `dim_client` → `dim_advisor` and `dim_security` → `dim_benchmark`. The foreign-key check reuses `check_referential_integrity()` from HW4.
- **Dates join on `dim_date[date]`, not `date_id`.** `fee_date`, `snapshot_date` and `txn_date` store calendar dates. All three match `dim_date[date]` 100% and `dim_date[date_id]` 0%. `dim_date[date]` is unique, so it can be the one side of a relationship. `date_id` stays the table's primary key, but no fact uses it.

**Key that can legitimately be blank.** `fact_transactions.security_id` is blank on 101,528 rows (34.0%). They are exactly the cash transactions: every Deposit (35,956), Withdrawal (29,830) and Advisory Fee (35,742) row is blank, and every Buy, Sell and Dividend row has a matching security. Cash moving into or out of an account doesn't involve a security, so a blank is correct here. No other foreign key has a blank.

**Columns that look like keys but are not foreign keys.**

- `dim_benchmark.ticker_proxy` (SPY, AGG, …) looks as if it points to `dim_security[ticker]`, but 0 of 8 values match. It is a descriptive label.
- `fact_portfolio_snapshot.year` and `month` are parts of `snapshot_date`; they agree on every row. The link to the calendar goes through `snapshot_date`.
- `fact_portfolio_snapshot.account_type` is a text attribute. No account dimension exists, so there is nothing for it to point to.

## Part B — Grain

| Fact table | Grain | Unique on |
|---|---|---|
| fact_fees | One row represents one fee charged to one client for one month. The type of fee (Advisory, Management, Custodial or Performance) is recorded on the row. | `client_id` + `fee_date` |
| fact_portfolio_snapshot | One row represents one client's account position (AUM, returns and cash share) for one month. | `client_id` + `snapshot_date` |
| fact_transactions | One row represents one transaction on one client's account on one day: a trade, a dividend, or a cash movement. | `txn_id` only |

**How the grains were proven.** `scripts/02_grain.py` tests each declared grain alongside coarser alternatives (client alone, client + year). For transactions, it also tests combinations of business columns. Every figure quoted below is pinned in the script, so it stops with an error if the data changes. Detail is in `reports/grain.csv`.

- **fact_fees:** `client_id` + `fee_date` has 0 duplicates in 122,197 rows, and every `fee_date` is the 1st of a month. So a client is charged at most one fee in a month. `fee_type` isn't needed to make a row unique, because client + month already is. It also isn't fixed per client: all 2,500 clients were charged more than one type over their history. So it describes the charge rather than being part of the grain. Not every month has a fee: 7,350 client-months have a snapshot but no fee. Every fee month does have a snapshot.
- **fact_portfolio_snapshot:** `client_id` + `snapshot_date` has 0 duplicates in 129,547 rows, and every date is the 1st of a month. Each client has exactly one `advisor_id`, `benchmark_id` and `account_type`, so there is one account per client and "client-month" is the same as "account-month". All 2,500 clients have an unbroken monthly series, with no missing months between their first and last snapshot.
- **fact_transactions:** no combination of business columns is a key, so the grain is the single event and only `txn_id` identifies it. Even client + date + type + security repeats on 1,238 rows (616 groups, the largest with 3 rows). For example, client 1 made two Deposits on 2024-09-25 ($94,893.52 and $26,587.27). These are separate events, not duplicate rows: no repeated group shares an amount, and no two rows match on every business column.

## Part C — Measures

**Definitions.**

- **Additive:** a measure that can be summed across every dimension.
- **Semi-additive:** a measure that can be summed across some dimensions but not others. Usually it can't be summed across time, because it is a balance.
- **Non-additive:** a measure that can't be summed across any dimension. It is a rate, a ratio or a price, and has to be recomputed from additive parts or weighted.

**How the classification was checked.** `scripts/03_measures.py` finds every numeric column in the eight tables (47 in total) and fails if one is left unclassified. It then tests the arithmetic each classification depends on, on every row: a blank or unparseable value fails the test rather than being skipped. The figures quoted below are pinned in the script.

**Summary:** of the 11 fact measures, 1 is additive (fee `amount`), 4 are semi-additive (`aum_basis`, `aum`, transaction `amount`, `shares`) and 6 are non-additive (`bps_charged`, `return_ytd`, `benchmark_return_ytd`, `active_alpha_ytd`, `cash_pct`, `price`). Detail is in `reports/measures.csv`.

### Fact measures

| Table | Column | Class | What that means for summing and averaging |
|---|---|---|---|
| fact_fees | `amount` | **Additive** | Dollars charged, so it can be summed across clients, advisors, fee types and months. Total fees are $204.68M. |
| fact_fees | `aum_basis` | **Semi-additive** | The AUM balance the fee was charged on (it equals the snapshot `aum` for the same client and month on all 122,197 fees). Sum it across clients within one month; across months, take the last month or the average month. |
| fact_fees | `bps_charged` | **Non-additive** | A rate. Never sum it, and don't take a simple average. Effective rate = `SUM(amount) × 12 × 10,000 / SUM(aum_basis)`. On every row, `amount` = `aum_basis × bps_charged / 10,000 / 12`, to within half a cent. |
| fact_portfolio_snapshot | `aum` | **Semi-additive** | A monthly balance (dated the 1st). Sum it across clients within a month: firm AUM in Dec 2024 is $12.73B across 2,325 clients. Never sum it across months: all 60 months added together give $566.68B, 44.5× the real balance. Across time, use the last month (or the average month for an average balance). |
| fact_portfolio_snapshot | `return_ytd` | **Non-additive** | A cumulative year-to-date percentage that resets each January. Comparing each month with the one before for the same client, the value moves 6.4× more going into January (33.4% on average) than in any other month (5.2%). The average size of the value is 5.1% in January and 32.1% in December. Across months, take the latest month of the year, not a sum. Across clients, use an AUM-weighted average. |
| fact_portfolio_snapshot | `benchmark_return_ytd` | **Non-additive** | One value per benchmark per month, copied onto every client using that benchmark. Summing across clients multiplies it by the number of clients. Read it per benchmark per month. |
| fact_portfolio_snapshot | `active_alpha_ytd` | **Non-additive** | Equals `return_ytd − benchmark_return_ytd` on every row. Aggregate the two returns first, then take the difference; never sum or average alpha directly. |
| fact_portfolio_snapshot | `cash_pct` | **Non-additive** | A share of AUM (0.01 to 0.08). Never sum it. The firm-level figure is AUM-weighted: `SUM(aum × cash_pct) / SUM(aum)`. |
| fact_transactions | `amount` | **Semi-additive** | Dollars that can be summed across clients, advisors, securities and dates, but **not across `txn_type`**. Every amount is positive, and the direction (money in or out) comes only from `txn_type`. Adding Deposits and Withdrawals (or Buys and Sells) together unsigned gives a meaningless total. Total it within one type, or sign it by type first (e.g. net flow = Deposits − Withdrawals), and then it can be added across everything. Advisory Fee transactions ($263.71M) and `fact_fees` ($204.68M) are separate sources (HW4 D-20), so never add them together. |
| fact_transactions | `shares` | **Semi-additive** | Can be summed across clients and dates, but only within one security and one `txn_type`. Shares of different securities are different units. Dividend rows carry `shares` too, but no shares are bought or sold on a dividend, so adding them to Buy or Sell shares mixes two different things. |
| fact_transactions | `price` | **Non-additive** | A price per share. Never sum it. Average trade price for one security = `SUM(amount) / SUM(shares)` over its Buy and Sell rows, leaving out Dividends for the same reason as `shares`. On every Buy, Sell and Dividend row, `amount` = `shares × price`. |

### Numeric columns that are not measures

| Table | Columns | Why not a measure |
|---|---|---|
| fact_fees | `fee_id`, `client_id`, `advisor_id` | Keys: count them, never sum them |
| fact_portfolio_snapshot | `snapshot_id`, `client_id`, `advisor_id`, `benchmark_id` | Keys |
| fact_portfolio_snapshot | `year`, `month` | Date parts of `snapshot_date`: group by them, never sum them |
| fact_portfolio_snapshot | `is_return_suspect` | 0/1 flag (3,875 rows flagged). Count flagged rows; use it as a filter, not a value |
| fact_transactions | `txn_id`, `client_id`, `advisor_id`, `security_id` | Keys |
| fact_transactions | `is_post_departure_txn` | 0/1 flag (2,410 rows flagged). Count flagged rows; use it as a filter |

### Numeric dimension attributes that should never be summed

A dimension row is repeated across every fact row that joins to it. Summing a dimension number through a fact relationship therefore multiplies it by the number of fact rows.

| Table | Columns | Why never sum |
|---|---|---|
| dim_advisor | `years_experience` | Describes an advisor; average it or group it into bands |
| dim_advisor | `aum_target_mm` | One target per advisor. Compare it to actual AUM; summing it through a fact repeats it on every row |
| dim_client | `age` | Describes a client; average it or group it into bands |
| dim_client | `initial_aum` | AUM at onboarding, a one-time value, not the current balance (use snapshot `aum` for that) |
| dim_client | `zip_code` | A code, not a number. Load it as Text so leading zeros are kept |
| dim_date | `year`, `quarter`, `month`, `week_of_year` | Calendar parts: group by them |
| dim_date | `is_month_end`, `is_quarter_end`, `is_year_end`, `is_trading_day` | 0/1 flags: filter on them |
| dim_security | `expense_ratio_bps` | A rate; average it weighted by holdings |
| All dimensions | `*_id` keys (`advisor_id`, `benchmark_id`, `client_id`, `date_id`, `security_id`) | Identifiers |

## Part E — Relationships and design questions

### (a) Transactions with no `security_id`

### (b) `advisor_id` in `dim_client` and the three fact tables

### (c) Joining on `dim_date[date]` vs `dim_date[date_id]`

### (d) Star or snowflake

## Part F — Reflection
