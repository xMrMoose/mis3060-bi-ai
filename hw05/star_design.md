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

### Fact measures

### Numeric columns that are not measures

### Numeric dimension attributes that should never be summed

## Part E — Relationships and design questions

### (a) Transactions with no `security_id`

### (b) `advisor_id` in `dim_client` and the three fact tables

### (c) Joining on `dim_date[date]` vs `dim_date[date_id]`

### (d) Star or snowflake

## Part F — Reflection
