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
│   ├── common.py                   ← shared paths, table loading, blank/type tests, check collector
│   ├── 01_keys.py                  ← Part A: PK uniqueness, FK integrity, date join column
│   ├── 02_grain.py                 ← Part B: grain uniqueness for each fact table
│   └── 03_measures.py              ← Part C: classify every numeric column, with evidence
├── data/
│   └── clean/                      ← the 8 Wildcat Capital Clean tables (read-only)
├── reports/
│   ├── keys_pk.csv                 ← Part A: one row per table
│   ├── keys_fk.csv                 ← Part A: one row per relationship
│   ├── grain.csv                   ← Part B: one row per candidate grain tested
│   └── measures.csv                ← Part C: one row per numeric column (47)
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
python hw05/scripts/02_grain.py
python hw05/scripts/03_measures.py
```

`01_keys.py` (a few seconds) proves every primary key and foreign key in `star_design.md` Part A. It
writes `reports/keys_pk.csv` (8 tables) and `reports/keys_fk.csv` (13 relationships), and stops with a
`KeyCheckError` if any check fails. It imports `check_referential_integrity()` from
`hw04/scripts/03_validate.py`, so the `hw04/` folder must be present.

`02_grain.py` (a few seconds) proves the grain of each fact table in `star_design.md` Part B. It tests
the declared grain and coarser alternatives, so the report shows both why the grain holds and why a
coarser one doesn't. The figures quoted in Part B are pinned in the script. It writes `reports/grain.csv`
and stops with a `GrainCheckError` if any check fails or a quoted figure changes.

`03_measures.py` (a few seconds) checks the `star_design.md` Part C classification. It finds every
numeric column in the 8 tables and fails if one is left unclassified. It then tests the arithmetic each
class depends on, for example fee = AUM × bps / 10,000 / 12, and that summing AUM across months
inflates it 44.5×. It writes `reports/measures.csv` and stops with a `MeasureCheckError` if any check
fails or a quoted figure changes.

All three scripts share the helpers in `common.py`, so Parts A and B treat blanks and types the same way.

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
| `02_grain.py` | The fee-type claim in Part B ("changes for every client") was only printed, never checked | Check added (0 of 2,500 clients have a single fee type), and the Part B wording now matches exactly what is tested |
| `02_grain.py` | Figures quoted in `star_design.md` (1,238 rows, 616 groups, 7,350 months, …) were not checked, though the text said the script would fail if a result changed | `EXPECTED` pins all 7 quoted figures; the script fails if any differs |
| `02_grain.py` | The fees alternative `fee_date + fee_type` could never fail, so it showed nothing about the declared grain | Replaced with coarser candidates `client_id + year` and `client_id` (same as snapshots) |
| `02_grain.py` | Uniqueness compared numbers as text, so `67311.3` and `67311.30` counted as different and a real duplicate could slip through | `shares`, `price`, `amount` are converted to numbers first. Fault test: a duplicate with amount `…330` now fails |
| `02_grain.py` | Gap check compared month span with row count, so a duplicated month and a missing month cancel out | Compares span with distinct months. Fault test: duplicate Feb + missing Mar now fails |
| `02_grain.py` | Advisor-per-client was checked for snapshots but not fees | Added for `fact_fees`. Fault test: an advisor change fails |
| `02_grain.py` | Helpers (`is_blank`, check collector) copied from `01_keys.py` could drift | Moved to `common.py`, used by both scripts; Part A reports byte-identical after the change |
| `02_grain.py` | `snapshot_date` parsed twice; date format rule in three places | Parsed once per table; one `parse_iso_date()` in `common.py` |
| `02_grain.py` | **Outcome** | All 8 fixed. Grains unchanged (3 proven, now 11 candidates tested); 3 fault-injection tests confirm the new checks |
| `03_measures.py` | Transaction `amount` was classed Additive, yet it can't be summed across `txn_type`, which breaks Part C's own definition | **My decision:** reclassified as semi-additive (additive across clients, advisors, securities and dates, not across `txn_type`; fully additive once signed by type) |
| `03_measures.py` | Part C says the fee identity holds "to within half a cent", but the script enforced $0.01, and the gap was skipped in the pinned-figure loop | `TOLERANCES` dict: fee and trade identities pinned at half a cent; alpha and `aum_basis` tolerances in the same place |
| `03_measures.py` | "60 months", 122,197 fees, the `cash_pct` range and the 47-column count were quoted but not pinned | All added to `EXPECTED` (17 pinned figures) |
| `03_measures.py` | `aum_basis` = `aum` was compared as text, so `125000.0` vs `125000` would fail falsely | Numeric comparison with a tolerance. Fault test: trailing zeros now pass |
| `03_measures.py` | Gap checks used `.max()` and `.mean()`, which skip NaN, so a blank value passed "on every row" claims | Every identity requires no NaN, and classified columns must be filled unless listed in `ALLOWED_BLANK`. Fault test: a blank `active_alpha_ytd` fails |
| `03_measures.py` | The "resets each January" evidence (mean January < mean December) can't tell year-to-date from since-inception | New test: month-on-month change for each client is 6.4× larger going into January than in other months |
| `03_measures.py` | The "real balance" month was hard-coded as `2024-12-01` | Uses the latest `snapshot_date`, which is also pinned |
| `03_measures.py` | Part C's average-price rule didn't exclude Dividends, contradicting the `shares` rule | Rule is now Buy/Sell only, in both the script and Part C |
| `03_measures.py` | Coverage ignored a numeric column with one stray text value | A column with ≥95% numeric values counts as numeric and must be classified and fully numeric. Fault test: a new column with one `n/a` fails |
| `03_measures.py` | Tolerances were scattered as magic numbers, and the same columns were parsed repeatedly | One `TOLERANCES` dict; each fact table's numeric columns parsed once |
| `03_measures.py` | **Outcome** | 9 fixed, 1 classification changed by my decision. 47 columns classified; fact measures 1 additive / 4 semi-additive / 6 non-additive; 3 fault-injection tests confirm the new checks |

## Status

- [ ] Part A — Keys
- [ ] Part B — Grain
- [ ] Part C — Measures
- [ ] Part D — Power BI model
- [ ] Part E — Relationships and design questions
- [ ] Part F — Reflection
