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

*(Run order and any arguments will be confirmed once the scripts are written.)*

## Claude Code Review Findings

| Script | What Claude Code flagged | What I did about it |
|---|---|---|
| `01_profile.py` | | |
| `02_clean.py` | | |
| `03_validate.py` | | |

## Status

- [ ] Part A — Audit
- [ ] Part B — Decision log
- [ ] Part C — Cleaning program
- [ ] Part D — Referential integrity and validation
- [ ] Part E — Business report
