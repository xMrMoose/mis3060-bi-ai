# HW4 Decision Log — Wildcat Capital Data Cleaning

One entry per issue found in the Part A audit ([reports/dq_summary_raw.csv](reports/dq_summary_raw.csv)),
written **before** the cleaning code for that issue. Issues deliberately left as is are logged too.
Finding IDs (F0xx) refer to `dq_summary_raw.csv`.

**Dimensions:** Validity · Completeness · Uniqueness · Consistency · Accuracy/Plausibility · Referential Integrity
**Decisions:** convert · standardize · fill · flag · quarantine · leave as is

## Summary

"Rows" is the number of rows each decision changes in the **clean output**. Quarantine runs first
(see cleaning order), so D-02, D-05 and D-06 are slightly lower than the raw audit counts: their other
rows belong to quarantined records and are kept untouched in quarantine.

| ID | Table / column | Decision | Rows |
|---|---|---|---:|
| D-01 | dim_client (clients 2501–2525) | quarantine | 25 |
| D-02 | dim_client.state | standardize | 77 (raw 78) |
| D-03 | dim_client.risk_profile | fill | 75 |
| D-04 | dim_advisor.certifications | standardize | 6 |
| D-05 | fact_transactions.security_id | convert | 197,044 (raw 197,175) |
| D-06 | fact_transactions.shares | convert | 835 (raw 836) |
| D-07 | fact_transactions.client_id | quarantine | 200 |
| D-08 | fact_transactions (inactive clients) | flag | 2,410 |
| D-09 | fact_transactions.txn_date | leave as is | 84,999 (44,262 trades) |
| D-10 | fact_transactions.security_id / shares / price | leave as is | 101,597 |
| D-11 | fact_portfolio_snapshot.return_ytd | convert | 300 |
| D-12 | fact_portfolio_snapshot.return_ytd / active_alpha_ytd | standardize | 891 |
| D-13 | fact_portfolio_snapshot.aum, fact_fees.aum_basis | flag | 420 / 386 |
| D-14 | fact_portfolio_snapshot.return_ytd | flag | 1,475 |
| D-15 | fact_fees.bps_charged | leave as is | 1 |
| D-16 | dim_security.sector / expense_ratio_bps | leave as is | 500 |
| D-17 | dim_benchmark.benchmark_id = 6 | leave as is | 1 |
| D-18 | dim_client.client_since | leave as is | 1,549 |
| D-19 | Type encodings across tables | leave as is | — |
| D-20 | fact_transactions (Advisory Fee) vs fact_fees | leave as is | 35,766 |
| D-21 | fact_transactions.shares (sold more than bought) | leave as is | 43,010 |
| D-22 | fact_transactions (dividends without a Buy) | leave as is | 7,128 |
| D-23 | dim_date.is_trading_day (market holidays) | leave as is | 47 |
| D-24 | fact_transactions.price (dispersion within security) | leave as is | 36,280 |
| D-25 | dim_client.zip_code vs state | leave as is | 2,211 |
| D-26 | dim_security.name (shared names) | leave as is | 6 |

The decisions add three flag columns: `flag_after_last_snapshot` (fact_transactions), `flag_aum_floor`
(fact_portfolio_snapshot and fact_fees) and `flag_return_outlier` (fact_portfolio_snapshot).

---

## Defects: fix or contain

## D-01: Duplicate clients with altered last names

| Field | Entry |
|---|---|
| **Table / column** | `dim_client`, all columns (client_id 2501–2525) |
| **Evidence** | F005: 50 rows (25 pairs) match on every column except `client_id` and `last_name`. Each of client_id 2501–2525 duplicates an earlier client (IDs 99–2421). In 23 pairs the last name is cut short (`Taylo` / `Taylor`, `Marti` / `Martin`); in 2 it has an extra letter (`Leen` / `Lee`, `Pacen` / `Pace`). F020: none of the 25 IDs appear in any fact table. |
| **Dimension violated** | Uniqueness, Accuracy |
| **Decision** | **quarantine** the 25 rows with client_id 2501–2525 to `quarantine_dim_client_duplicates.csv`, recording the original client_id each one duplicates |
| **Justification** | Same person, same age, zip, AUM, start date and advisor: one client entered twice. The originals have the complete names and own all the activity, so removing the copies loses no facts. Keeping them would inflate the client count by 25 (1%) and the AUM under management. |
| **Risk** | If any pair were two real people, we would undercount clients. Very unlikely: 12 identical attributes including `initial_aum` to the cent. Verify after cleaning that no fact row references a quarantined ID (it should stay 0). |

## D-02: State names spelled out

| Field | Entry |
|---|---|
| **Table / column** | `dim_client.state` |
| **Evidence** | F001: 78 rows are not 2-letter codes: Pennsylvania 25, Florida 15, New York 14, New Jersey 13, California 5, Illinois 4, Texas 2. The other 2,447 use USPS codes. |
| **Dimension violated** | Validity, Consistency |
| **Decision** | **standardize** to USPS codes with an explicit 7-entry name→code map |
| **Justification** | Unambiguous: each name has exactly one code. Without it, state slicers and maps split Pennsylvania clients across "PA" and "Pennsylvania". |
| **Risk** | Minimal. The script asserts that every value is a valid code afterwards, and fails on any unmapped name instead of guessing. |

## D-03: Blank risk profile

| Field | Entry |
|---|---|
| **Table / column** | `dim_client.risk_profile` |
| **Evidence** | F026: 76 blanks (75 after D-01 removes one duplicate). They span every tier (Retail 49, HNW 18, UHNW 9). No other column predicts risk profile: benchmark assignment varies within every risk profile. |
| **Dimension violated** | Completeness |
| **Decision** | **fill** with the explicit label `Unknown` |
| **Justification** | A risk profile can't be inferred without inventing a suitability assessment. `Unknown` invents nothing: it makes the gap visible in Power BI (a named slicer value rather than "(Blank)"), and compliance can list clients who need a suitability review. |
| **Risk** | Someone could read `Unknown` as a real profile category. Mitigation: document it in `README_clean.md` and log every change in `value_changes.csv`. |

## D-04: Literal text "None" in certifications

| Field | Entry |
|---|---|
| **Table / column** | `dim_advisor.certifications` |
| **Evidence** | F010: 6 of 25 advisors have the text `None`. |
| **Dimension violated** | Consistency (a null-like token that means a real value) |
| **Decision** | **standardize** `None` → `No Certification` |
| **Justification** | Here `None` is a real answer: the advisor holds no certifications. Default pandas parsing and many BI loaders turn the string `None` into a null, which would turn "known: none" into "unknown". |
| **Risk** | None material. 6 rows, deterministic mapping. |

## D-05: security_id stored as float text

| Field | Entry |
|---|---|
| **Table / column** | `fact_transactions.security_id` |
| **Evidence** | F004 / F008: all 197,175 non-blank values end in `.0` (`45.0`), so a text join to `dim_security.security_id` (`45`) matches 0%. After stripping `.0`, 100% match. |
| **Dimension violated** | Validity, Referential Integrity |
| **Decision** | **convert** to integer text (`45.0` → `45`); blanks stay blank (see D-10) |
| **Justification** | It's a storage artifact: a column with blanks was saved as float. The key value is unchanged. |
| **Risk** | A non-integer value (e.g. `45.5`) would be silently truncated. Mitigation: assert that every value matches `^\d+\.0$` before converting, and that RI is 100% afterwards. |

## D-06: Negative shares on Buy transactions

| Field | Entry |
|---|---|
| **Table / column** | `fact_transactions.shares` |
| **Evidence** | F006 / F007: 836 rows, all `txn_type = Buy`, have negative shares while `amount` is positive. F037: for all 836, \|shares\| × price = amount within $0.01. |
| **Dimension violated** | Validity (sign rule), Consistency |
| **Decision** | **convert** shares to their absolute value |
| **Justification** | In this table direction comes from `txn_type`, and every other share count is positive. The amount reconciles exactly once the sign is flipped, so the repair is verified rather than assumed. This continues the HW2 finding that the error is limited to `shares`. |
| **Risk** | If these were reversals or cancelled buys, a positive count overstates holdings. Weak case: amounts are positive and typed as Buy. Assert that `shares × price = amount` holds for all security rows after the fix. |

## D-07: Transactions for clients that don't exist

| Field | Entry |
|---|---|
| **Table / column** | `fact_transactions.client_id` |
| **Evidence** | F009: 200 rows with 200 distinct client_ids (2702–3192), all above the dimension's maximum of 2525. One transaction each, dated 2020-02-18 to 2024-12-19, total $10,888,495.37 (0.067% of all transaction value). Advisor IDs are valid. |
| **Dimension violated** | Referential Integrity |
| **Decision** | **quarantine** to `quarantine_fact_transactions_orphan_client.csv` |
| **Justification** | Creating placeholder clients would invent tier, risk profile and AUM. Any join to `dim_client` would drop or blank these rows anyway. One transaction per unknown ID looks like a key-assignment error in the source system. |
| **Risk** | Transaction totals drop by $10.9M (0.067%). If the clients are real but missing from the extract, the source team can restore them from the quarantine file, which keeps every original column. |

## D-08: Inactive clients transacting after their last snapshot

| Field | Entry |
|---|---|
| **Table / column** | `fact_transactions` (clients with `dim_client.is_active = False`) |
| **Evidence** | F025: 2,410 transactions from 131 of 175 inactive clients fall after the month of their last snapshot (Buy 689, Sell 482, Dividend 439, Advisory Fee 284, Deposit 278, Withdrawal 238). Active clients have 0 such rows. No fees are charged after the last snapshot. |
| **Dimension violated** | Consistency (cross-table), Accuracy/Plausibility |
| **Decision** | **flag**: add `flag_after_last_snapshot` (0/1) to fact_transactions |
| **Justification** | Snapshots and fees agree that the account closed, but the transactions say otherwise. We can't tell which side is wrong: closing liquidations or late postings would be real, while key errors would not. Flagging keeps the rows so analysts can include or exclude them. |
| **Risk** | Leaving them unflagged would misstate activity and AUM flows for closed accounts. Deleting them could lose real closing transactions. Flagging avoids both, but anyone who ignores the flag still counts them. |

## D-11: Returns stored as percent strings

| Field | Entry |
|---|---|
| **Table / column** | `fact_portfolio_snapshot.return_ytd` |
| **Evidence** | F003: 300 values like `9.28%`. F035: for all 300, value / 100 = `benchmark_return_ytd + active_alpha_ytd` within 1e-4. Without dividing by 100, 270 of them would read as returns above 100%. |
| **Dimension violated** | Validity, Consistency (unit) |
| **Decision** | **convert**: strip `%` and divide by 100 |
| **Justification** | Every other row stores returns as decimal fractions. The alpha identity (return − benchmark = alpha) confirms both the scale and the value for every converted row. |
| **Risk** | Nearly none, since every row is checked against two other columns. Assert that the alpha identity holds for 100% of rows afterwards. |

## D-12: Scientific notation in return columns

| Field | Entry |
|---|---|
| **Table / column** | `fact_portfolio_snapshot.return_ytd` (135), `active_alpha_ytd` (756) |
| **Evidence** | F013 / F014: values like `-1.9e-05`. Python parses them, but they are a second text format in the column. |
| **Dimension violated** | Consistency (format) |
| **Decision** | **standardize** to plain decimal notation, rewritten exactly (every one of the 891 values has at most 6 decimal places, the column's precision, so no rounding is needed) |
| **Justification** | Some BI and Excel imports read `1.9e-05` as text, or interpret it by locale. The value doesn't change. |
| **Risk** | None to the values: the rewrite is exact (Decimal arithmetic, no rounding). Check that every numeric value is unchanged and that the alpha identity still holds. |

## D-13: AUM held at a $1,000 floor

| Field | Entry |
|---|---|
| **Table / column** | `fact_portfolio_snapshot.aum` (420 rows), `fact_fees.aum_basis` (386 rows) |
| **Evidence** | F011 / F015 / F021: `1000.0` occurs 420× in snapshots and 386× in fees, while the next most common value occurs only twice. Every fee row at 1000.0 matches a snapshot at 1000.0 for the same client-month. **No AUM anywhere is below $1,000**, and 405 more rows sit between $1,000 and $1,100. All 92 clients affected are Retail. Accounts fall to exactly 1000.0 (206 times from a higher value), stay there, and grow back from it. |
| **Dimension violated** | Accuracy/Plausibility |
| **Decision** | **flag**: add `flag_aum_floor` (0/1) to both tables; keep the value |
| **Justification** | This is a floor in the source system, not a stand-in for unknown values. True AUM is somewhere between $0 and $1,000 and can't be recovered from any other column, so replacing it would invent data. The value is real enough for totals ($420K across all floor rows is immaterial against a ~$4.4M mean AUM), but a flag lets performance analysis exclude these rows. |
| **Risk** | Small: fees on floor rows may be overstated by a few dollars. The larger effect is on returns (D-14). |

## D-14: Implausible year-to-date returns

| Field | Entry |
|---|---|
| **Table / column** | `fact_portfolio_snapshot.return_ytd` |
| **Evidence** | F012: 1,475 rows (after D-11 converts the 300 percent strings; the raw audit counted 1,473) outside [−90%, +100%]: 977 above +100% (144 clients, max 9,467%) and 498 below −90% (95 clients). 476 of the 498 large losses and 505 of the 977 large gains belong to clients who hit the $1,000 floor (D-13). Rows above +100% have a median AUM of $71.6K, against $484.7K overall. The alpha identity holds on every one of these rows. **The bounds are a chosen plausibility threshold, not a hard limit:** only a return below −100% is impossible for an unleveraged account. The bounds were set well outside the observed normal range: benchmark returns span −24.0% to +27.4%, and the 1st–99th percentile of `return_ytd` is −57.4% to +79.4%. |
| **Dimension violated** | Accuracy/Plausibility |
| **Decision** | **flag**: add `flag_return_outlier` (0/1); keep values |
| **Justification** | The values are internally consistent: they come from small accounts with large deposits and withdrawals relative to their balance, and from moves on and off the floor. The return calculation doesn't adjust for cash flows. Recomputing returns would require a different methodology, and capping them would invent data. Averaging these unflagged would distort the committee's view of performance. |
| **Risk** | A few real high returns get flagged; a flag excludes nothing by default. Unflagged averages remain distorted, so `README_clean.md` should tell BI users to filter on the flag. |

---

## Legitimate structure or accepted: leave as is

## D-09: Transactions dated on weekends

| Field | Entry |
|---|---|
| **Table / column** | `fact_transactions.txn_date` |
| **Evidence** | F022: 44,262 Buy/Sell rows fall on non-trading days: 40,649 on weekends and 3,613 on weekday NYSE holidays that `dim_date` wrongly marks as trading (see D-23; added after QA, so the original evidence cited only the 40,649 weekend trades). Across *all* types, 84,999 transactions (28.45%) of transactions are on weekends, almost exactly the 2/7 (28.57%) a uniform spread over all 7 days would give. Deposits and fees show the same rate as trades. |
| **Dimension violated** | Accuracy/Plausibility (trades should settle on trading days) |
| **Decision** | **leave as is**; document as a known limitation |
| **Justification** | It's a uniform, systemic pattern, not a set of bad rows. It looks like a booking- or entry-date convention rather than a trade date. Moving dates to the next trading day would invent dates, and flagging 28% of the table adds noise without telling anyone which rows are wrong. |
| **Risk** | Any analysis by day of week or trading day is unreliable. Monthly and yearly aggregates, which is how HW5 uses the data, are unaffected. |

## D-10: Blank security fields on cash transactions

| Field | Entry |
|---|---|
| **Table / column** | `fact_transactions.security_id`, `shares`, `price` |
| **Evidence** | F029–F031 / F036: 101,597 blanks in each column, all on Deposit (35,981), Withdrawal (29,850) and Advisory Fee (35,766). No Buy/Sell/Dividend row has a blank, and no cash row has a value (0 violations either way). |
| **Dimension violated** | None. Structural. |
| **Decision** | **leave as is** (null) |
| **Justification** | Cash movements have no security. Filling with 0 or a dummy security would create fake holdings and drag down average-price measures. Same conclusion as HW2. |
| **Risk** | A BI model must allow a null foreign key on `security_id`. That goes in `README_clean.md`. |

## D-15: One fee above 100 bps

| Field | Entry |
|---|---|
| **Table / column** | `fact_fees.bps_charged` |
| **Evidence** | F002: fee_id 68809 (client 1402, Management, 2024-07-01) at 100.38 bps. The fee amount reconciles (108,401.76 × 100.38 / 120,000 = 90.68). The client's management fee usually runs 82–100 bps (mean 89.3), and 6 fees in the table exceed 99 bps. |
| **Dimension violated** | Accuracy/Plausibility (only against my assumed 100 bps cap) |
| **Decision** | **leave as is** |
| **Justification** | The 100 bps cap was my assumption, not a documented rule. The row is consistent with its own amount and close to the client's normal range. For Part D validation the cap becomes 0–150 bps. |
| **Risk** | If Wildcat Capital does cap fees at 1%, the client was overcharged by $0.34. Immaterial, but worth one line in the report's limitations. |

## D-16: ETF / non-ETF blanks in dim_security

| Field | Entry |
|---|---|
| **Table / column** | `dim_security.sector` (219 blank), `expense_ratio_bps` (281 blank) |
| **Evidence** | F027 / F028 / F032: every sector blank is an ETF and every expense-ratio blank is a non-ETF, with 0 exceptions either way. |
| **Dimension violated** | None. Structural. |
| **Decision** | **leave as is** |
| **Justification** | ETFs span sectors, and single securities have no expense ratio. Filling either would be false. |
| **Risk** | Sector charts show a "(Blank)" bar that is really "ETF / multi-sector". Documented in `README_clean.md`. |

## D-17: Benchmark with no references

| Field | Entry |
|---|---|
| **Table / column** | `dim_benchmark.benchmark_id = 6` (MSCI Emerging Markets) |
| **Evidence** | F019 / F050: no snapshot or security references benchmark 6. |
| **Dimension violated** | None |
| **Decision** | **leave as is** |
| **Justification** | Dimensions often hold members with no facts yet, and removing it would break future references. |
| **Risk** | None. |

## D-18: client_since earlier than the date table

| Field | Entry |
|---|---|
| **Table / column** | `dim_client.client_since` |
| **Evidence** | F051: 1,549 clients started before 2020-01-01, the first date in `dim_date` (earliest 2015-01-01). No fact row predates its client's start date. |
| **Dimension violated** | None |
| **Decision** | **leave as is** |
| **Justification** | `client_since` is a descriptive attribute, not one of the 3 date-table relationships. `dim_date` covers the 2020–2024 fact period by design. |
| **Risk** | Anyone who joins `client_since` to `dim_date` loses 61% of clients. Documented: don't build that relationship. |

## D-19: Type encodings a default parser would break

| Field | Entry |
|---|---|
| **Table / column** | `dim_client.zip_code` (leading zeros, e.g. `03897`), `primary_account_type` / `fact_portfolio_snapshot.account_type` (`529` among text values), booleans (`True`/`False` in `is_active` and `is_etf`, `0`/`1` in `dim_date` flags) |
| **Evidence** | Profile: `zip_code` is 100% 5-digit with leading zeros. `account_type` is 26,882 int-looking values plus 102,665 text. |
| **Dimension violated** | Validity, but only if parsed carelessly |
| **Decision** | **leave as is** in the CSVs; set column types in `README_clean.md` (zip and account type as text, booleans as true/false) |
| **Justification** | The stored values are correct. The danger is in how a reader parses them. Changing booleans to one encoding would alter dimension columns other courses or HW5 may expect. |
| **Risk** | A careless import turns `03897` into 3897 and `529` into a number. Mitigated by the type table. |

## D-20: Advisory Fee transactions don't match fact_fees month by month

| Field | Entry |
|---|---|
| **Table / column** | `fact_transactions` (`txn_type = Advisory Fee`) vs `fact_fees.amount` |
| **Evidence** | Per client-month, Advisory Fee debits are a median of 3.11× the fee table's total for that month, and 1,933 of 30,679 debit months have no fee row. |
| **Dimension violated** | Consistency (cross-table), but likely a difference in grain |
| **Decision** | **leave as is**; test a quarterly reconciliation in Part D before calling it a defect |
| **Justification** | A ratio near 3 suggests fees accrue monthly but are debited quarterly. That's a billing convention, not an error. Nothing should be changed until that hypothesis is tested. |
| **Risk** | If Part D shows they don't reconcile at any grain, one of the two fee sources is wrong, and that becomes a reported limitation. |
| **Outcome (Part D)** | **The hypothesis was rejected.** In `03_validate.py` R4, per client-quarter, debits match accruals within 1% in 0.53% of client-quarters against all fee types and 0.11% against `fee_type = Advisory` only. Month, year and lifetime grains also fail (best case 1.5%). Debits occur about 3.4 times a client-year on random days, and total $263.7M against $204.7M accrued (129%). The decision stays **leave as is**: there's no basis for choosing which source is right. It's reported as a limitation, and revenue should be measured from `fact_fees` (the source that reconciles to AUM × bps) until finance explains the debits. |

---

## Added after QA review: defects with no source to repair from

A QA pass against the brief found that the audit had never tested holdings, price consistency, the
market calendar or addresses. Five checks were added to `01_profile.py` (findings F016, F017, F018,
F023, F024, F033), and the non-trading-day check (F022) now also counts weekday market holidays. Every resulting decision is **leave as is**, so no cleaning code was needed and
the clean tables are unchanged. The entries are logged here so the limitations are on record.

## D-21: Clients sell more shares than they bought

| Field | Entry |
|---|---|
| **Table / column** | `fact_transactions.shares` (Buy / Sell running position per client and security) |
| **Evidence** | F023: 43,010 of 59,755 Sells (72.0%) take the client's position in that security below zero; 22,713 of 38,813 client-security pairs go negative at some point. **This is not explained by holdings from before 2020.** Clients who joined in 2020 or later go short at the same rate (71.5% against 72.3%), and for 6,215 of their 15,056 client-security pairs the very first trade is a Sell. |
| **Dimension violated** | Consistency (facts disagree with each other), Accuracy |
| **Decision** | **leave as is**; document as a limitation |
| **Justification** | Each transaction is internally consistent (shares × price = amount), but the trades weren't recorded against any holdings. The extract has no positions or opening-balance table, so the correct sequence or quantity can't be recovered. Changing shares or deleting Sells would invent or destroy cash flows. |
| **Risk** | Any holdings or position report built by summing Buys minus Sells is wrong for most clients. Use `fact_portfolio_snapshot.aum` for account value, not reconstructed positions. If some clients transferred securities in (no transfer transactions exist), part of this would be legitimate. The 2020+ client evidence suggests that can't be the main cause. |

## D-22: Dividends on securities the client never bought

| Field | Entry |
|---|---|
| **Table / column** | `fact_transactions` (`txn_type = Dividend`) vs the client's Buy history |
| **Evidence** | F024: 7,128 of 53,864 dividends (13.2%) pay on a security the client has no Buy for. For clients who joined in 2020 or later it is 2,734 of 20,938 (13.1%), so pre-2020 holdings don't explain it. |
| **Dimension violated** | Consistency (cross-table), Accuracy |
| **Decision** | **leave as is**; document |
| **Justification** | Same root cause as D-21: income and trades aren't linked to holdings. The dividend cash was received according to the record, and nothing in the extract identifies the correct security. |
| **Risk** | Income-by-security and yield analysis are unreliable. Total dividend income per client is still a usable cash figure. |

## D-23: Market holidays marked as trading days

| Field | Entry |
|---|---|
| **Table / column** | `dim_date.is_trading_day` |
| **Evidence** | F017: all 47 weekday NYSE holidays in 2020–2024 are marked `is_trading_day = 1` (e.g. 2020-01-01, 2020-12-25, 2022-07-04, 2024-11-28). The column is simply "weekday = 1, weekend = 0". 3,613 Buy/Sell trades fall on these holidays (counted in D-09). The holidays were rebuilt from NYSE's standard rules, since the extract has no exchange calendar. |
| **Dimension violated** | Accuracy |
| **Decision** | **leave as is**; document that `is_trading_day` means "weekday" |
| **Justification** | Fixing it needs an external calendar that isn't part of the extract, and rules rebuilt in code would miss one-off closures. The fix belongs in the source date dimension. The impact is small (47 of 1,827 days, 2.6%), and D-09 already makes trading-day analysis unreliable. |
| **Risk** | A "trading days" measure built on `is_trading_day` overstates by about 9 days a year and misses the 3,613 holiday trades. The audit uses the rebuilt calendar instead. Low, since reporting is monthly. |

## D-24: The same security trades at very different prices

| Field | Entry |
|---|---|
| **Table / column** | `fact_transactions.price` (Buy / Sell) |
| **Evidence** | F018: 36,280 of 143,311 trades (25.3%) are priced below half or above double their security's median trade price. The median security's highest trade price is 44× its lowest. |
| **Dimension violated** | Accuracy/Plausibility |
| **Decision** | **leave as is**; document |
| **Justification** | Each price reconciles to its own amount and shares, so cash values are internally consistent. The extract has no market price series to repair against, and replacing prices would change amounts that already match. |
| **Risk** | Price-based analysis (average cost, unrealised gain, price trends per security) is meaningless. Cash amounts and AUM are unaffected. |

## D-25: Zip codes don't match the client's state

| Field | Entry |
|---|---|
| **Table / column** | `dim_client.zip_code` vs `state` |
| **Evidence** | F016: for 2,211 of 2,447 clients with a valid state code (90.4%), the zip's first digit belongs to a different USPS region than the state (e.g. client 1: PA with zip 75726, a Texas range). |
| **Dimension violated** | Consistency, Accuracy |
| **Decision** | **leave as is**; `state` is the geography of record |
| **Justification** | Nothing says which field is right. The state is the field the business reports on, and it is now standardized (D-02). Changing zips would invent addresses. |
| **Risk** | Zip-level maps or distance analysis would place clients in the wrong state. Documented: don't use `zip_code` for geography. |

## D-26: Same name on different securities

| Field | Entry |
|---|---|
| **Table / column** | `dim_security.name` |
| **Evidence** | F033: 3 names appear twice (6 securities), each pair with different tickers. Two pairs also differ in asset class or ETF status (e.g. "Jones Inc Fund" as both a Fixed Income and an Alternative ETF). |
| **Dimension violated** | None. Legitimate structure. |
| **Decision** | **leave as is** |
| **Justification** | Fund families commonly reuse a sponsor name across products. The keys and tickers are unique, and the attributes differ, so these aren't duplicates. Merging them would combine different investments. |
| **Risk** | A report that groups by name instead of ticker would merge them. Report on `ticker`. |

---

## Verified, no action needed

These cross-checks passed in Part A, and the cleaning will use them to verify repairs:

- `fact_fees.amount` = `aum_basis × bps_charged / 120,000` within $0.01 on all 122,197 rows
- `active_alpha_ytd` = `return_ytd − benchmark_return_ytd` on all 129,547 rows (after D-11)
- `fact_fees.aum_basis` = the same client-month's `fact_portfolio_snapshot.aum` on all 122,197 rows
- Fact `advisor_id` matches `dim_client.advisor_id` in all 3 fact tables; snapshot `account_type` matches `primary_account_type`
- `client_tier` agrees with the `initial_aum` band (Retail < $500K ≤ HNW < $5M ≤ UHNW) for all 2,525 clients
- `dim_date` derived columns (year, quarter, month, week, names, period-end flags, weekend = non-trading) agree with `date`

## Cleaning order (for `02_clean.py`)

1. **Quarantine** (D-01, D-07). Dimension duplicates go first, then fact orphans are checked against the
   de-duplicated dimension.
2. **Convert formats** (D-05, D-11, D-12). These are lossless and make the reconciliation checks possible.
3. **Fix values that can be verified** (D-02, D-04, D-06). Each fix is checked against a reconciliation.
4. **Fill** (D-03).
5. **Flag** (D-08, D-13, D-14). Runs last, on the final rows, so the flag counts match the clean output.
6. **Check** `raw rows = clean rows + quarantined rows` for all 8 tables.

*Revised after the Claude Code review of `02_clean.py`.* The first plan converted formats before
quarantining. As a result, the orphan-transaction quarantine file held 131 converted `security_id`s and
1 sign-flipped `shares` value instead of the raw values, and `value_changes.csv` logged 133 changes to
rows that aren't in the clean output. Quarantining first keeps quarantined records exactly as received
(a source team can restore them as is) and makes every logged change apply to a clean row. No
decision changed, only the order and the D-02/D-05/D-06 counts above.
