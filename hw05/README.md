# HW5: Modeling the Wildcat Capital Data as a Star Schema in Power BI

MIS3060 Business Intelligence with AI — Week 8 (dimensional modeling and Power BI)

Assignment brief: [HW05_Star_Schema_and_Power_BI.md](HW05_Star_Schema_and_Power_BI.md)
Power BI mechanics: [powerbi_guide.md](powerbi_guide.md)

## Folder Structure

```
hw05/
├── README.md                       ← this file (structure, how to run, Claude Code findings)
├── HW05_Star_Schema_and_Power_BI.md ← assignment brief
├── powerbi_guide.md                ← Part D how-to (loading, relationships, date table)
├── star_design.md                  ← Parts A, B, C, E and F
├── scripts/
│   └── 01_keys.py                  ← Part A: PK uniqueness, FK integrity, date join column
├── data/
│   └── clean/                      ← the 8 Wildcat Capital Clean tables (read-only)
├── reports/
│   ├── keys_pk.csv                 ← Part A: one row per table
│   └── keys_fk.csv                 ← Part A: one row per relationship
└── powerbi/
    ├── hw05.pbix                   ← Part D: saved model
    └── model_view.png              ← Part D: full Model view screenshot
```

## Source Data (`data/clean/`)

The instructor's `Wildcat Capital Clean/` release. Row and column counts verified against the brief.

| File | Rows | Cols | Role |
|---|---:|---:|---|
| `dim_advisor.csv` | 25 | 7 | Advisors |
| `dim_benchmark.csv` | 8 | 4 | Performance benchmarks |
| `dim_client.csv` | 2,500 | 14 | Clients |
| `dim_date.csv` | 1,827 | 12 | Calendar, 2020–2024 |
| `dim_security.csv` | 500 | 8 | Securities and ETFs |
| `fact_fees.csv` | 122,197 | 8 | Monthly fee charges |
| `fact_portfolio_snapshot.csv` | 129,547 | 14 | Monthly account snapshots |
| `fact_transactions.csv` | 298,572 | 10 | Trades, income, cash flows, fee debits |

## How to Run

From the repository root, with the course virtual environment active:

```
python hw05/scripts/01_keys.py
```

`01_keys.py` (a few seconds) proves every primary key and foreign key in `star_design.md` Part A. It
writes `reports/keys_pk.csv` (8 tables) and `reports/keys_fk.csv` (13 relationships), and stops with a
`KeyCheckError` if any check fails. It imports `check_referential_integrity()` from
`hw04/scripts/03_validate.py`, so the `hw04/` folder must be present.

## Process Note: How AI Was Used

*To be completed.*

## Claude Code Review Findings

| Script | What Claude Code flagged | What I did about it |
|---|---|---|
| `01_keys.py` | Whole-number test (`\d+`) accepted leading zeros, so `'07'` and `'7'` passed as distinct keys but would collide once Power BI casts them to Whole Number | Keys must be canonical integers (no leading zero). Fault test: a `'07'`/`'7'` pair now fails |
| `01_keys.py` | `\d` matches non-ASCII digits, and there was no Int64 range limit | Pattern is ASCII `[0-9]`, at most 18 digits |
| `01_keys.py` | Date foreign keys were labeled "Date" without checking that they parse as dates | Fact dates and `dim_date[date]` must parse as `YYYY-MM-DD` |
| `01_keys.py` | Blank detection was inconsistent: the HW4 RI function strips whitespace, but the script compared to `""` exactly | One `is_blank()` helper (strip, then empty) used everywhere. Fault test: a whitespace `security_id` on a cash row is now treated as blank |
| `01_keys.py` | Each report was written before its check ran, so a failure could leave a new `keys_pk.csv` next to a stale `keys_fk.csv` | Every check runs and failures are collected; both reports are written together, then the script raises |
| `01_keys.py` | An unknown `txn_type` would be treated silently as a security transaction | Every `txn_type` must be one of the 3 cash or 3 security types. Fault test: `Transfer` fails |
| `01_keys.py` | Year/month check compared year as text and month via `astype(int)`, which crashes on a blank month | Both compared numerically against the parsed `snapshot_date`. Fault test: a blank month now fails with a clear message |
| `01_keys.py` | A missing HW4 script raised a bare importlib error | Clear `KeyCheckError` naming the HW4 dependency |
| `01_keys.py` | PK and FK lists duplicate HW4's `PKS` and `RELATIONSHIPS` and could drift apart | **Kept by choice:** the lists are the Part A answer, so they stay written out here. A new check 0 fails if they differ from HW4's |
| `01_keys.py` | Blank-by-type counts scanned the table once per `txn_type` | One `groupby().agg(["sum", "size"])` |
| `01_keys.py` | **Outcome** | 9 of 10 fixed, 1 kept with an agreement check. Results on the clean data are unchanged (8 PKs, 13 FKs, all pass); 4 fault-injection tests confirm the new checks catch problems |

## Status

- [ ] Part A — Keys
- [ ] Part B — Grain
- [ ] Part C — Measures
- [ ] Part D — Power BI model
- [ ] Part E — Relationships and design questions
- [ ] Part F — Reflection
