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
│   ├── 03_measures.py              ← Part C: classify every numeric column, with evidence
│   ├── 04_relationships.py         ← Part E: model paths, conformed dimensions, (a)–(d) figures
│   └── 05_questions.py             ← Part F: each manager question, single visual vs correct answer
├── data/
│   └── clean/                      ← the 8 Wildcat Capital Clean tables (read-only)
├── reports/
│   ├── keys_pk.csv                 ← Part A: one row per table
│   ├── keys_fk.csv                 ← Part A: one row per relationship
│   ├── grain.csv                   ← Part B: one row per candidate grain tested
│   ├── measures.csv                ← Part C: one row per numeric column (47)
│   └── relationships.csv           ← Part E: the 13 relationships as built, active flag, notes
└── powerbi/
    ├── hw05.pbix                   ← Part D: saved model (21.8 MB, under GitHub's 100 MB limit)
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
python hw05/scripts/04_relationships.py
python hw05/scripts/05_questions.py
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

`04_relationships.py` (a few seconds) holds the 13 designed relationships. It confirms they are the
Part A foreign keys and that they match the relationships Power BI reports for `hw05.pbix` (see below),
and traces every filter path to prove that no two tables
have more than one active path. It also computes the figures quoted in `star_design.md` Part E: the
advisor paths, and the benchmark meaning on snapshots vs transactions. It writes
`reports/relationships.csv` and stops with a `RelationshipCheckError` if a check fails or a quoted
figure changes. It imports `FOREIGN_KEYS` from `01_keys.py`.

`05_questions.py` (a few seconds) answers the three Part F questions two ways: what a single Power BI
visual with the default Sum shows, and the correct answer. Examples: year-end AUM vs 12 summed monthly
balances, and net new money vs deposits plus withdrawals. It pins the 21 figures Part F quotes and stops
with a `QuestionCheckError` if one changes.

**Exporting the model's relationships.** `04_relationships.py` reads
`powerbi/relationships_export.csv`, which comes from Power BI itself, not from a hand-written list:

1. In Power BI Desktop, open the **DAX query view** (fourth icon on the left rail).
2. Run `EVALUATE INFO.VIEW.RELATIONSHIPS()`.
3. Copy the result grid with its headers, paste it into a text file, and save it as
   `powerbi/relationships_export.csv`. Tab- or comma-separated both work.

Redo the export whenever a relationship changes in the model.

All four scripts share the helpers in `common.py`, so Parts A and B treat blanks and types the same way.

## Power BI Model (Part D)

Built by hand in Power BI Desktop (not Apporto), following `powerbi_guide.md`, from the 8 files in
`data/clean/`. Open `powerbi/hw05.pbix` in Power BI Desktop.

- **Types:** every column set in Power Query: `*_id` keys Whole Number (`security_id` blank on cash
  rows), dates Date, amounts, AUM, rates and returns Decimal Number, `zip_code` and `account_type`
  Text, `is_active` and `is_etf` True/False, 0/1 flags Whole Number.
- **Relationships:** 13 relationships, all many-to-one with single-direction filtering. 11 are active
  and 2 are inactive (`star_design.md` Part E):
  - `dim_client → dim_advisor` would be a second path to `dim_advisor`.
  - `dim_security → dim_benchmark` would mix the client's benchmark with the security's.
- **Dates:** fact dates join `dim_date[date]`, and `dim_date` is marked as the date table on `date`.
  Auto date/time is still on. Its only hidden date table is for `dim_client[client_since]`, which
  isn't joined to `dim_date`. `04_relationships.py` lists it separately from the designed
  relationships.
- **Summarize by:** set to None on the 41 numeric columns that Part C says never to sum. Only the 5
  additive and semi-additive measures default to Sum.
- **Checks page:** row-count card (Count of each primary key), with all 8 tables matching the brief.
  A ticker × transaction amount table shows the expected `(Blank)` row for the 101,528 cash
  transactions. An advisor slicer filters all three facts.

## Process Note: How AI Was Used

The brief asks for scripts to be drafted in **Claude Desktop**, run in VS Code, and reviewed by
**Claude Code** before each commit. As in HW4, this assignment departed from that split: the scripts and
`star_design.md` were **drafted in Claude Code** (inside VS Code), from my instructions and decisions.
The **Power BI model (Part D) I built myself** in Power BI Desktop, following `powerbi_guide.md`. Claude
Code walked through each step with me and checked my screenshots and the exported relationship list,
but didn't create the `.pbix`.

Separation between drafting and checking came from four things:

- **A separate review pass before every commit.** Claude Code's `/code-review` ran as an independent
  review agent on each script. Its findings and my responses are in the table below: 47 findings
  across 5 scripts, 45 fixed, 1 kept with an agreement check, and 1 reclassification decided by me.
- **Script output as the source of truth.** Every figure in `star_design.md` is pinned in the script
  that computes it, so a changed number fails the script instead of leaving the write-up stale.
  Fault-injection tests (deliberately broken copies of the data) confirmed the checks catch problems.
- **The model checked against Power BI itself.** `04_relationships.py` compares the design with the
  relationships Power BI exports (`INFO.VIEW.RELATIONSHIPS()`), not with a hand-typed copy.
- **My own decisions on the judgement calls.** I chose the semi-additive classification of transaction
  `amount` (Part C) and the inactive `dim_security → dim_benchmark` relationship (Part E (d)), after
  reviewing the evidence.

**Corrections made along the way:**
- Claude Code's first Power Query type table missed `aum_target_mm`, and I caught it.
- The review of `05_questions.py` found that the Part D advisor slicer on `last_name` selects both
  Johnsons, so Part E (b) was corrected.
- A per-advisor ratio was written before it was computed, and was replaced with the computed figure
  before commit.

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
| `04_relationships.py` | The relationship list said "exactly as built", but `hw05.pbix` still had `dim_security → dim_benchmark` active, and nothing tied the hand-typed active flags to the real model | The script now reads the relationships Power BI reports (`INFO.VIEW.RELATIONSHIPS()` export) and fails on any difference in active flag, cardinality or direction. Tested on a simulated export: the old model (#12 active) fails with that relationship named. The model was then updated (#12 inactive) and re-exported |
| `04_relationships.py` | "Different groups of clients" (S&P 500 example) was asserted, not measured | Measured: 2,376 clients trade S&P-benchmarked securities, only 666 have an S&P 500 portfolio, and 71.5% of those trades are by other clients. Part E wording now gives these figures |
| `04_relationships.py` | Several quoted figures weren't pinned (701 clients, 0 Conservative Blend securities, 2,500 clients, the `date_id` range 1 to 1,827) | Added to `EXPECTED` (30 figures pinned) |
| `04_relationships.py` | Question (c) was a fixed print statement, not a computation | Computes the match to `date` and to `date_id` over all fact dates, plus the `date_id` range |
| `04_relationships.py` | Names quoted in Part E (Danielle Johnson, S&P 500, Conservative Blend, the 3 portfolio benchmarks) weren't checked | `EXPECTED_NAMES`, looked up from `dim_advisor` and `dim_benchmark` |
| `04_relationships.py` | Client benchmark took each client's first snapshot without checking that it never changes | Check: every client has exactly one portfolio benchmark |
| `04_relationships.py` | The agreement check compared sets, so a duplicated relationship would pass and inflate the counts | Also checks that no relationship is listed twice |
| `04_relationships.py` | Redundant per-path groupby; lookup dict rebuilt inside a loop; repeated maps | Groupby removed (it follows from the every-row match); `REACHES` constant; maps computed once |
| `04_relationships.py` | **Outcome** | All 10 fixed. The model is checked against Power BI's own relationship list, not a hand-typed copy. On the real export, two further adjustments: skip Power BI's hidden Auto date/time relationship (1, for `client_since`), and compare names case-insensitively, because `INFO.VIEW.RELATIONSHIPS` reports `dim_date[date]` as `[Date]` in `ToColumn` while its relationship text says `[date]`. Result: 13 of 13 match (11 active, 2 inactive, all many-to-one, single direction) |
| `05_questions.py` | **Q1 visual merged two advisors**: `dim_advisor[last_name]` on rows puts Danielle and Robert Johnson in one row. The same applied to the Part D slicer, so Part E (b) had quoted advisor 1's counts (5,008 fees …) as what that "Johnson" slicer showed, when it selects both advisors (9,408 / 9,971 / 23,862) | Q1 visual uses last + first name. Part E (b) corrected: advisor 1's counts are given as computed figures, and the shared last name is explained. `04_relationships.py` now pins the Johnson counts and checks that no two advisors share a full name |
| `05_questions.py` | Q3 visual put `dim_date[month]` (1–12) on the axis, which merges the same month across 5 years | Axis is year + month; the script counts 60 year-months |
| `05_questions.py` | "Same error in a by-advisor version" was asserted, not computed | Computed and pinned: for 2024, 25 advisors at 10.6× to 10.7×. (My first wording, 9.9×–11.9×, was a guess; corrected before commit) |
| `05_questions.py` | The snapshot-to-calendar flag join was an inner join, so dropped rows would also give the pinned 0 | Left join with `validate="many_to_one"`; fails if any snapshot date is missing from `dim_date` |
| `05_questions.py` | The flag test compared with `'1'` only, so a re-encoded flag would also give 0 | Checks that both flags are 0/1 with both values present |
| `05_questions.py` | The advisor-path check compared summed frames: NaN cells could fail falsely, and offsetting errors could pass | Row-by-row: fee advisor equals client's advisor on every fee |
| `05_questions.py` | "Before December 2024" relied on the data happening to end then | `LAST_MONTH` pinned; the script fails if the data ends elsewhere |
| `05_questions.py` | Deposits and withdrawals were summed twice; the print recomputed figures | Totals taken from the monthly pivot; prints reuse the computed figures |
| `05_questions.py` | A missing `Withdrawal` type would crash with KeyError before the checks ran | Pivot reindexed to both types |
| `05_questions.py` | **Outcome** | All 9 fixed, including a correction to Part E (b). 21 Part F figures pinned |

## Status

- [x] Part A — Keys
- [x] Part B — Grain
- [x] Part C — Measures
- [x] Part D — Power BI model
- [x] Part E — Relationships and design questions
- [x] Part F — Reflection
