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

*(Run order for 02 and 03 will be confirmed once those scripts are written.)*

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
| `02_clean.py` | | |
| `03_validate.py` | | |

## Status

- [x] Part A — Audit
- [ ] Part B — Decision log
- [ ] Part C — Cleaning program
- [ ] Part D — Referential integrity and validation
- [ ] Part E — Business report
