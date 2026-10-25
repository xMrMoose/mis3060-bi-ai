# HW4: Cleaning the Wildcat Capital Data

MIS3060 Business Intelligence with AI — Weeks 6–8 (data cleaning, wrangling, referential integrity)

Assignment brief: [HW04_Data_Cleaning.md](HW04_Data_Cleaning.md)

## Folder Structure

```
hw04/
├── README.md                  ← this file (structure, how to run, Claude Code findings)
├── HW04_Data_Cleaning.md      ← assignment brief
├── decision_log.md            ← Part B: one entry per issue, written BEFORE cleaning code
├── scripts/
│   ├── 01_profile.py          ← Part A: generic profiler + four groups of DQ checks
│   ├── 02_clean.py            ← Part C: incremental, asserted cleaning program
│   └── 03_validate.py         ← Part D: RI function, rule checks, reconciliations, scorecard
├── data/
│   ├── dirty/                 ← the 8 raw source tables (read-only, never modified)
│   ├── clean/                 ← the 8 cleaned tables + README_clean.md
│   └── audit/                 ← cleaning_log.csv, value_changes.csv, quarantine_*.csv
└── reports/
    ├── profile_raw.csv
    ├── dq_summary_raw.csv
    ├── data_quality_scorecard.csv
    ├── ri_results.csv         ← Part D detail: 13 relationships, raw and clean
    ├── rule_results.csv       ← Part D detail: every business rule, raw and clean
    ├── reconciliations.csv    ← Part D detail: cross-table reconciliations
    ├── outliers_iqr.csv       ← Part D detail: IQR fences and flag counts
    └── cleaning_report.md     ← Part E: business report for the portfolio committee
```

`data/dirty/` holds the raw extract (what the brief calls the "raw" files). Scripts read from it
but never write to it.

## Source Data (`data/dirty/`)

| File | Rows | Cols | Role |
|---|---:|---:|---|
| `dim_advisor.csv` | 25 | 7 | Advisors |
| `dim_client.csv` | 2,525 | 14 | Clients |
| `dim_date.csv` | 1,827 | 12 | Calendar, 2020–2024 |
| `dim_security.csv` | 500 | 8 | Securities and ETFs |
| `dim_benchmark.csv` | 8 | 4 | Performance benchmarks |
| `fact_fees.csv` | 122,197 | 8 | Monthly fee charges |
| `fact_portfolio_snapshot.csv` | 129,547 | 13 | Monthly account snapshots |
| `fact_transactions.csv` | 298,772 | 9 | Trades, income, cash flows, fee debits |

All files are read as text (`dtype=str`, `keep_default_na=False`) and converted column by column on purpose.

## How to Run

From the repository root, with the course virtual environment active:

```
python hw04/scripts/01_profile.py
python hw04/scripts/02_clean.py
python hw04/scripts/03_validate.py
```

`01_profile.py` with no arguments audits all 8 tables (about 1 minute) and writes
`reports/profile_raw.csv` and `reports/dq_summary_raw.csv`. Given file paths, it runs only the
generic column profiler on any CSV: `python hw04/scripts/01_profile.py some_file.csv`.

`02_clean.py` (about 15 seconds) reads `data/dirty/` and writes the 8 clean tables to `data/clean/`
and the audit trail to `data/audit/`. It stops with a `CleaningError` if any fix doesn't do what
`decision_log.md` claims, and writes nothing until every table passes.

`03_validate.py` (about 20 seconds) runs the same checks on `data/dirty/` and `data/clean/`. It writes
`reports/data_quality_scorecard.csv` plus four detail files. Run it after `02_clean.py`, because R5 reads
the quarantine files. `check_referential_integrity(fact_df, fact_key, dim_df, dim_key)` is
self-contained and reused in HW5.

**IQR outliers: does "flagged" mean "wrong"? No.** Wealth data is right-skewed. Fences on all clients
flag 10.04% of `initial_aum`, but 0 clients once the fences are set within each client tier, and every
flagged value passes all business rules. A flag marks an unusual value to look at, not an error.

## Claude Code Review Findings

| Script | What Claude Code flagged | What I did about it |
|---|---|---|
| `01_profile.py` | Left joins to `dim_client` (and fee→snapshot join) would multiply fact rows if a key were duplicated, inflating counts above 100% | De-duplicate the dimension key / snapshot grain before every cross-table merge |
| `01_profile.py` | Unparseable dates (NaT) counted as "disagrees with date" in `dim_date` and snapshot year/month rules, so one bad date became several ERRORs | Rules now apply only to rows whose date parsed; parse failures are reported once, by the profiler |
| `01_profile.py` | Date range checks compared raw strings, so a non-ISO date like `03/15/2021` was also reported out of range | Range checks compare parsed dates |
| `01_profile.py` | Tier-vs-AUM rule put clients with unparseable `initial_aum` into the UHNW band (the `np.select` default) | Rule skips rows with no numeric AUM |
| `01_profile.py` | `txn_type` matched case-sensitively, so a dirty `buy` would be treated as a cash-only type | Match on trimmed, lower-cased `txn_type` |
| `01_profile.py` | `client_since` checks counted blanks, and the "activity before client_since" rule ignored activity earlier in the start month | Compare parsed dates; daily transactions compare to the exact start date, monthly facts to the start month |
| `01_profile.py` | "Mixed formats" treated `1500` and `1500.25` as different formats | Whole numbers and decimals now count as one numeric format |
| `01_profile.py` | Cross-table placeholder check was hard-coded to the string `1000.0` | Reuses the generic value-spike detector and confirms the same value on the same client-month in both tables |
| `01_profile.py` | Minor: value shapes computed twice per column; snapshot recency compared as strings | Compute once; compare parsed dates |
| `01_profile.py` | **Outcome** | All 10 fixed. Findings unchanged on this data (46: 9 ERROR / 11 WARN / 26 INFO): the fixes make the checks sound when rerun on clean data in Part D |
| `02_clean.py` | **Quarantine files held modified rows**: orphan transactions were quarantined after `security_id`/`shares` fixes, so 131 `security_id`s and 1 `shares` in the quarantine file differed from raw, and `value_changes.csv` logged 133 changes to rows that aren't in the clean output (confirmed against the output files) | Reordered: quarantine runs first. The script now verifies that quarantined rows equal the raw rows and that every logged change applies to a clean row. Decision-log counts updated (D-05 197,044, D-06 835, D-02 77) with the reason |
| `02_clean.py` | Every safety check was a bare `assert`, which `python -O` removes | Replaced with `check()` raising `CleaningError`; verified the script runs with `-O` |
| `02_clean.py` | Clean files were written inside the validation loop, so a failure would leave a mix of new and stale outputs | Validate all 8 tables and the raw hashes first, then write everything |
| `02_clean.py` | D-08: an inactive client with no snapshots would never be flagged (NaT comparisons are False) | No snapshot is treated as "after the last snapshot". (The only such client, 2515, is a quarantined duplicate with no transactions, so the count is unchanged) |
| `02_clean.py` | D-06 reconciliation treated NaN as passing | Check `~(gap <= 0.01)` so unparseable shares/price/amount count as failing |
| `02_clean.py` | D-12 code (exact rewrite) didn't match the decision log (round to 6 dp) | Checked: all 891 values already have ≤ 6 dp, so the exact rewrite is correct; decision log wording fixed to match |
| `02_clean.py` | `iloc[0]` on an empty selection would crash D-12 if a column had no e-notation | Example printed only when there are matches |
| `02_clean.py` | Several "after" checks were tautologies (D-03, D-04, D-07, D-14) | Replaced with independent checks: values must fall in the allowed set with unmasked values unchanged; clean + quarantined dollars must equal raw; return flag rebuilt from benchmark + alpha must agree |
| `02_clean.py` | Duplicated relabel logic in D-03/D-04 | Shared `relabel()` helper |
| `02_clean.py` | D-13 fee-vs-snapshot flag check ran in one direction only | Now checks that the flags agree in both directions on every fee client-month |
| `02_clean.py` | **Outcome** | All 10 fixed. Independent diff of raw vs clean: 199,228 changed cells = 199,228 logged changes; untouched tables byte-identical to raw |
| `03_validate.py` | R4 compared Advisory Fee debits against *all* fee types, so a FAIL could come from how the test was built | R4 now runs under both readings (all fee types, and `fee_type = Advisory` only). Both fail (0.53% / 0.11%), so the D-20 conclusion doesn't depend on that choice |
| `03_validate.py` | R5 "clean + quarantined = raw" compared only dollar totals, and unparseable amounts summed as 0, so a dropped row could go unnoticed | R5 also checks row counts and fails if any amount doesn't parse |
| `03_validate.py` | Completeness counted only exact `""` as missing, so placeholders like `N/A` or whitespace would count as filled | Placeholder tokens and whitespace-only cells count as missing. `None` in certifications is deliberately excluded because D-04 established it means "no certification" |
| `03_validate.py` | Calendar rule didn't check `is_quarter_end`, `is_year_end` or `week_of_year` | All derived columns are checked; the docstring notes that weekday holidays can't be checked without an exchange calendar |
| `03_validate.py` | Unparseable dates grouped into one fake `<NA>Q<NA>` quarter in R4 | They become NaN and are dropped by the group-by |
| `03_validate.py` | R2/R3 `drop_duplicates` on `client_id` would hide conflicting duplicates and depend on row order | A key whose duplicates disagree maps to NaN and fails the check |
| `03_validate.py` | IQR `flagged_pct` used all rows as denominator while `n` counted parseable values | Same denominator (`n`) for both |
| `03_validate.py` | `> 0` rules were implemented as `>= 0.01` | Strict `gt=0` bound |
| `03_validate.py` | `pct_rule_pass` / `pct_completeness` had no zero-denominator guard | Return blank (N/A) like the other metrics |
| `03_validate.py` | The printed "flagged ≠ wrong" sentence hard-coded its numbers | Numbers read from the outlier results computed in the same run |
| `03_validate.py` | **Outcome** | All 10 fixed. Scorecard unchanged; R4 split into two readings (both FAIL); R5 now also proves row counts |

## Status

- [x] Part A — Audit
- [x] Part B — Decision log
- [x] Part C — Cleaning program
- [x] Part D — Referential integrity and validation
- [x] Part E — Business report
