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

### The model built in Part D

All 13 foreign keys from Part A became relationships, so none was omitted. Every relationship is **many-to-one with a single cross-filter direction**: the dimension filters the fact, never the reverse. 11 are active and 2 are inactive.

| # | From (many) | To (one) | Active | Why |
|---|---|---|---|---|
| 1–3 | `fact_fees[fee_date]`, `fact_portfolio_snapshot[snapshot_date]`, `fact_transactions[txn_date]` | `dim_date[date]` | Yes | Conformed date dimension; see (c) |
| 4–6 | `client_id` on all three facts | `dim_client[client_id]` | Yes | Conformed client dimension |
| 7–9 | `advisor_id` on all three facts | `dim_advisor[advisor_id]` | Yes | Conformed advisor dimension; see (b) |
| 10 | `fact_transactions[security_id]` | `dim_security[security_id]` | Yes | Blank on cash rows; see (a) |
| 11 | `fact_portfolio_snapshot[benchmark_id]` | `dim_benchmark[benchmark_id]` | Yes | The client's portfolio benchmark |
| 12 | `dim_security[benchmark_id]` | `dim_benchmark[benchmark_id]` | **No** | By choice; see (d) |
| 13 | `dim_client[advisor_id]` | `dim_advisor[advisor_id]` | **No** | Would be a second path to `dim_advisor`; see (b) |

**Conformed dimensions.** `dim_date`, `dim_client` and `dim_advisor` each connect directly to all three fact tables, so one slicer on any of them filters fees, snapshots and transactions at the same time. That makes them the shared axes for comparing the three facts. `dim_security` filters only transactions, and `dim_benchmark` (with #12 inactive) filters only snapshots.

**How the model was checked.** `scripts/04_relationships.py` holds the 13 designed relationships and confirms they are the Part A foreign keys. It also compares them with the relationships Power BI reports for `hw05.pbix`, exported with `INFO.VIEW.RELATIONSHIPS()`: active flag, cardinality and cross-filter direction must all match. It traces every filter path (one side to many side) and proves that no two tables are joined by more than one active path, which is Power BI's rule. It also computes every figure below; these are pinned in the script. Detail is in `reports/relationships.csv`. The Part D checks page confirmed the model in Power BI: every row count matches the brief, the `(Blank)` ticker row appears, and an advisor slicer filters all three facts.

### (a) Transactions with no `security_id`

101,528 transactions (34.0%) have no `security_id`. They are exactly the **Deposit, Withdrawal and Advisory Fee** rows, and every Buy, Sell and Dividend has a security (Part A). These rows move cash into or out of the account, or charge a fee against it, and no security is bought or sold. A blank key is the correct way to record "no security", so **it is not a defect**. Making up a placeholder security would be worse, because it would show up as a fake ticker in every security report.

In Power BI, these rows appear as a `(Blank)` member under `dim_security`. The Part D check showed one `(Blank)` row, holding the cash amount. Any `(Blank)` on another dimension would mean an orphan key, and Part A showed there are none. The key stays Whole Number so the relationship works for the other 197,044 rows. The only caution is for reports: a security-level visual should filter to trade types, or label `(Blank)` as "Cash", so the cash rows aren't read as an unnamed security.

### (b) `advisor_id` in `dim_client` and the three fact tables

`dim_advisor` can be reached two ways: directly from each fact, or through `dim_client` (`fact → dim_client → dim_advisor`). Power BI allows only one active path between two tables. **I kept the three direct fact → `dim_advisor` relationships active (#7–9) and made `dim_client → dim_advisor` inactive (#13).**

- **It keeps the star shape:** every fact is one step from every dimension it uses, so filters are simple to follow and quick to run.
- **It records the right advisor:** the `advisor_id` on a fee, snapshot or transaction records who handled that event. The `advisor_id` on the client is only the client's *current* advisor. If a client is ever reassigned, the direct path keeps history right: past fees stay with the advisor who earned them. Through `dim_client`, they would move to the new advisor.
- **Today, both give the same numbers:** the fact's `advisor_id` equals the client's advisor on all 550,316 fact rows, and rows per advisor are identical through either path. So the choice protects future data rather than changing current results.

**Trade-off:** a slicer on `dim_advisor` doesn't filter the `dim_client` table itself. In the Part D check, an advisor slicer filtered all three fact counts, but the count of `dim_client` stayed at 2,500. For one advisor, Danielle Johnson (advisor 1), the facts filter to 5,008 fees, 5,304 snapshots and 12,661 transactions, while the client card still shows 2,500 rather than her 107 clients.

The Part D slicer used `last_name`, and two advisors share it: Danielle Johnson (advisor 1) and Robert Johnson (advisor 5). Selecting "Johnson" therefore selects both, and shows 9,408 fees, 9,971 snapshots and 23,862 transactions. An advisor slicer should use `advisor_id` or first and last name together; no two advisors share a full name. "Clients per advisor" therefore has to be counted from a fact (distinct `client_id` in snapshots). The alternative is to switch on #13 in a DAX measure with `USERELATIONSHIP`, which is why I kept it as an inactive relationship instead of deleting it.

### (c) Joining on `dim_date[date]` vs `dim_date[date_id]`

**I joined on `dim_date[date]`.** The facts store calendar dates (`2024-12-01`) and have no `date_id` column. All three fact date columns match `dim_date[date]` 100% and `dim_date[date_id]` 0% (Part A). `date_id` is a plain row number (1 to 1,827), so joining a date to it would match nothing.

`date` can serve as the one side because it is unique and never blank. It is also the column `dim_date` is marked as a date table on, which is what time-intelligence DAX needs. `date_id` remains the table's primary key, but no relationship uses it.

### (d) Star or snowflake

**Yes, two relationships connect one dimension to another:** `dim_client → dim_advisor` and `dim_security → dim_benchmark`. With both active, the model would be a small snowflake. **I kept both, but inactive**, so all filtering follows a star (dimension → fact only), while the links stay available to DAX through `USERELATIONSHIP`.

- **`dim_client → dim_advisor` (#13):** this one *had* to be inactive, because it would add a second path from `dim_advisor` to every fact (see (b)).
- **`dim_security → dim_benchmark` (#12):** Power BI would have let this one stay active, because it creates no second path. I made it inactive because **"benchmark" means two unrelated things** in this data:
  - on `fact_portfolio_snapshot`, it is the **client's** portfolio benchmark;
  - through `dim_security`, it is each **security's** benchmark.

  The two hardly overlap:
  - **Different sets:** client portfolios use 3 benchmarks (S&P 500, 60/40 Blend, Conservative Blend), while securities use 6.
  - **Rare matches:** only 9.4% of the 197,044 security trades are in a security whose benchmark matches the client's portfolio benchmark.

  With #12 active, one benchmark slicer would apply both meanings at once.
  - **Conservative Blend:** selecting it would show 50,117 snapshots for its 967 clients but **0 transactions**, because no security is benchmarked to it, even though those clients made 115,882 transactions.
  - **S&P 500:** it would show 36,528 snapshots for 701 clients next to 39,440 trades in 101 S&P-benchmarked securities, presented as if they were one group. They are largely different clients: 2,376 clients trade those securities, and only 666 of them have an S&P 500 portfolio. 71.5% of the trades come from clients with a different portfolio benchmark.

  With #12 inactive, a benchmark slicer filters portfolio snapshots only, which is its single clear meaning. A security's own `asset_class` and `sector` in `dim_security` still describe the trades.

## Part F — Reflection

There is one question per fact table. Each was answered twice in `scripts/05_questions.py`: once as a single Power BI visual with the default Sum would show it, and once correctly. All figures quoted are pinned in the script.

| # | Manager's question | Fact table | One visual, no DAX? | Schema change that would fix it |
|---|---|---|---|---|
| 1 | How much fee revenue did each advisor bring in each year? | fact_fees | **Yes** | None needed |
| 2 | What was the firm's (and each advisor's) AUM at the end of each year? | fact_portfolio_snapshot | **No** (Sum adds 12 monthly balances) | Date snapshots at the month end, so the calendar's year-end flag selects them |
| 3 | How much net new money (deposits − withdrawals) came in each month? | fact_transactions | **No** (Sum adds deposits *and* withdrawals) | A transaction-type dimension with a sign, plus a signed amount |

### Q1. Fee revenue by advisor and year: answerable in one visual

**Visual:** a matrix with `dim_advisor[last_name]` and `dim_advisor[first_name]` on rows, `dim_date[year]` on columns and **Sum of `fact_fees[amount]`** as values. Add `fee_type` as a column level for the split by fee type. Both name columns are needed, because Danielle and Robert Johnson share a last name (Part E (b)).

This works without DAX for two reasons. Fee `amount` is the one fully additive measure (Part C), so summing it across advisors and years is correct. Advisor and date are conformed dimensions with active direct relationships, so both filter `fact_fees` with no workaround. In 2024 the firm earned **$48.71M** in fees, and the top advisor was **Jeffery Wagner** with **$3.18M**. The result is the same through the inactive `dim_client → dim_advisor` path, because the fact advisor always equals the client's advisor (Part E (b)).

**Limits of the same model:**
- **Effective fee rate:** the natural follow-up, "what fee rate is each advisor earning?", can't be answered in one visual. `bps_charged` is non-additive, so a default Sum or Average gives a wrong number. It needs a DAX measure, `SUM(amount) × 12 × 10,000 / SUM(aum_basis)`.
- **Two fee sources:** this answer uses `fact_fees`. It shouldn't be compared with or added to the Advisory Fee transactions, which are a separate source (Part C).

### Q2. AUM at each year end: not answerable in one visual

**What a single visual shows:** `dim_date[year]` with Sum of `aum` gives **$135.46B for 2024**. The real year-end AUM, the December snapshot, is **$12.73B**. Every year comes out **10.6× to 12.4× too high**, because the visual adds up to 12 monthly balances of the same money (`aum` is semi-additive, Part C). It isn't exactly 12×, because clients join and leave during the year. A by-advisor version has the same error: for 2024, each of the 25 advisors' totals is 10.6× to 10.7× their December AUM.

**The workarounds are fragile:**
- **December filter:** a visual-level filter `dim_date[month] = 12` gives the right year-end figures. But it has to be remembered on every AUM visual, and any visual without it is silently wrong.
- **Calendar flags:** the calendar's own flags, which should be the natural tool, don't work. **0 snapshots fall on a day `dim_date` marks `is_month_end` or `is_year_end`**, because every snapshot is dated the 1st of its month. Filtering to year end therefore returns nothing.
- **Latest snapshot per client:** a "latest snapshot per client" rule would also be wrong. It would keep the **175 clients** whose last snapshot is before December 2024 in today's AUM, after they had left.

**Schema change:** store each snapshot on its **period-end date** (the last day of the month it describes), or add a `period_end_date` column joined to `dim_date`. `dim_date[is_year_end]`, `is_quarter_end` and `is_month_end` then select exactly one balance per client per period. "Year-end AUM" becomes a slicer choice instead of a filter someone has to remember. This would also resolve a real ambiguity: today, nothing says whether the `2024-12-01` snapshot is the opening or the closing balance for December.

**What schema can't fix:** a balance still can't be summed across time. "AUM as of the end of whatever period is selected" needs a semi-additive DAX measure (last date in the filter context), which is HW6 material.

### Q3. Net new money by month: not answerable in one visual

**What a single visual shows:** a matrix with `dim_date[year]` and `dim_date[month]` on rows (both, because `month` alone is 1–12 and would merge the same month across five years) and Sum of `fact_transactions[amount]`, filtered to Deposits and Withdrawals. Its total is **$3.31B**. Deposits ($1.82B) and withdrawals ($1.49B) are *added*, because every amount is stored as a positive number and the direction lives only in `txn_type` (Part C). The real net new money is **$327.44M**, 10× smaller.

**The workaround is weak:** putting `txn_type` on columns shows deposits and withdrawals side by side. The reader then has to subtract them by eye for each month, and the visual's total column still adds them. That's two numbers and mental arithmetic, not an answer. (The correct figure is positive in all 60 months: every month was a net inflow.)

**Schema change:**
1. Make `txn_type` a small dimension (`dim_txn_type`) instead of a text column on the fact, with:
   - a `direction` for cash: +1 for Deposit, Sell and Dividend; −1 for Withdrawal, Buy and Advisory Fee;
   - a `flow_category` (External flow, Trade, Income, Fee).
2. Store a `signed_amount` on the fact: `amount × direction`.

Net new money is then one visual: Sum of `signed_amount`, sliced by `flow_category = External flow`. The same column answers net trading (Buy vs Sell) and net cash movement with no DAX. HW5 allows no new tables or columns, so this is a recommendation for the next version of the warehouse, not a change made here.

### What this says about the model

The model answers questions about the **additive** measure (fees) directly, and the conformed date, client and advisor dimensions make those answers easy to slice. It **cannot** safely answer the two most common wealth-management questions, "how much are we managing?" and "how much new money came in?", with plain visuals. One is a balance stored at the start of the month; the other is an unsigned amount whose sign lives in a text column. Both failures look plausible on screen: $135B of AUM and $3.3B of inflows are believable numbers. That is why Part C's classification matters. HW6's DAX measures can work around both problems. The schema changes above would remove them for anyone building a report.
