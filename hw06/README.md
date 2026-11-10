# HW6: DAX Measure Library — AUM & Performance

MIS3060 Business Intelligence with AI — Weeks 9–10 (DAX measures, Claude as a DAX assistant)

Assignment brief: [HW06_DAX_Measure_Library.md](HW06_DAX_Measure_Library.md)
Power BI mechanics: [powerbi_dax_guide.md](powerbi_dax_guide.md)

## Folder Structure

```
hw06/
├── README.md                       ← this file (structure, how to run, Claude Code findings, mismatches)
├── HW06_DAX_Measure_Library.md     ← assignment brief
├── powerbi_dax_guide.md            ← measure patterns, metadata export, getting numbers out of Power BI
├── data/
│   └── clean/                      ← the 8 Wildcat Capital Clean tables (read-only, pandas side)
├── powerbi/
│   ├── hw06.pbix                   ← posted Wildcat_Star_Model.pbix + _Measures table + Measures page
│   ├── measures.md                 ← Part A documentation and Part C answers
│   └── export_powerbi_values.dax   ← Part B: DAX query that produces powerbi_values.csv
├── scripts/
│   ├── 01_reconcile_measures.py    ← Part B: independent pandas recompute vs Power BI values
│   └── 02_design_questions.py      ← Part C: computes and pins every figure the answers quote
├── reports/
│   ├── powerbi_values.csv          ← Part B input: measure, slice, value (exported from DAX query view)
│   ├── measure_reconciliation.csv  ← Part B output: one row per measure × slice, with match flag
│   └── design_questions.csv        ← Part C output: question, figure, value
└── claude/
    ├── model_metadata.md           ← Part D: the three INFO.VIEW query results
    ├── dax_session.md              ← Part D: prompt(s) and Claude's full response(s)
    └── verification.md             ← Part D: how Claude's measure was tested and judged
```

## Source Data (`data/clean/`)

The instructor's `Wildcat Capital Clean/` release, the same files as `hw05/data/clean/`.

| File | Rows | Cols | Role |
|---|---:|---:|---|
| `dim_advisor.csv` | 25 | 7 | Advisors |
| `dim_benchmark.csv` | 8 | 4 | Performance benchmarks |
| `dim_client.csv` | 2,500 | 14 | Clients |
| `dim_date.csv` | 1,827 | 12 | Calendar, 2020–2024 |
| `dim_security.csv` | 500 | 8 | Securities and ETFs |
| `fact_fees.csv` | 122,197 | 8 | Monthly fee charges |
| `fact_portfolio_snapshot.csv` | 129,547 | 14 | Monthly account snapshots (1st of the month) |
| `fact_transactions.csv` | 298,572 | 10 | Trades, income, cash flows, fee debits |

## Power BI Model

`powerbi/hw06.pbix` starts from the posted `Wildcat_Star_Model.pbix`, so every reconciliation uses the
same model. All measures go in a `_Measures` table.

- **Measures:** 17 in `_Measures`:
  - `Total Fees` and `Net Flows`, from the ICEs;
  - `AUM (naive SUM)`, kept only to show the mistake;
  - measures 1–11, with their LY/PM companions;
  - `Ending Clients Display`, a text version used only on the card (see below).

  DAX, pattern and meaning for each are in `powerbi/measures.md`.
- **Formats:**
  - currency with 2 decimals;
  - percentages with 2 decimals;
  - `Fee Yield (bps)` as a decimal with 2 decimals;
  - `Ending Clients` as a number with a thousands separator;
  - `Alpha Signal` and `Ending Clients Display` as text.
- **Measures page:** cards for Ending AUM, Ending Clients, Avg AUM per Client and Top 10 Client Share; a
  table by `dim_date[year]`; and a table by `dim_client[client_tier]` with a visual-level filter
  `dim_date[year]` = 2024. The file is saved with this page open.
- **Display issue, resolved with a workaround: the Ending Clients card showed "2K" instead of 2,325.**
  The measure itself was always correct: it returns 2,325 and reconciles exactly (Part B). The problem
  was only how Power BI's new card visual displayed it. I kept trying fixes and none worked:
  - display units None on the card;
  - the card's per-series settings;
  - changing the measure's format string (`0`, `0.00`, `#,0`, `#,0.00`);
  - deleting the card and rebuilding it.

  The saved report showed the card's display units already set to None, the same setting that works on
  the Ending AUM / Avg AUM per Client card. **Workaround:** I created
  `Ending Clients Display = FORMAT ( [Ending Clients], "#,##0" )` and put it on the card instead. As text,
  the card can't rescale it, so it shows "2,325". It is display-only: every calculation still uses
  `Ending Clients`, and the text version is reconciled at the grand total like every other measure.
- **Placeholder column:** `_Measures` still has the one-row `Column` that **Enter data** creates. The
  guide says to delete it, but Power BI wouldn't: right-click offered no Delete from model option, and
  the Delete key did nothing. No measure uses it, and it doesn't affect any result.

## How to Run

From the repository root, with the course virtual environment active:

```
python hw06/scripts/01_reconcile_measures.py
python hw06/scripts/02_design_questions.py
```

`02_design_questions.py` (a few seconds) computes the evidence for the four Part C answers in
`powerbi/measures.md`. All 79 figures the answers quote are pinned in `EXPECTED`. The script exits 1 if
any figure changes, or if it computes a figure that isn't pinned, and exits 2 on bad input.
`reports/design_questions.csv` is written only when every figure is confirmed. The SUMX total in (a)
was also run in Power BI's DAX query view and matches to the cent.

`01_reconcile_measures.py` takes about 2 seconds. Exit code 0 means every row matches, 1 means at least one mismatch (listed on
screen), and 2 means bad input, such as a missing required slice, an unknown measure, or a fact date
outside `dim_date`. On exit 2 no report is written, and any previous report is deleted first so a stale
"all match" file can't be mistaken for the current result.

**Refreshing `reports/powerbi_values.csv`.** The Power BI side comes from Power BI itself:

1. In Power BI Desktop, open `powerbi/hw06.pbix` and go to **DAX query view**.
2. Paste in `powerbi/export_powerbi_values.dax` and run it. It returns 92 rows (`measure, slice, value`)
   covering every slice Part B requires. Values are converted to text so they come out unrounded, not as
   `$12.73bn`.
3. Copy the result grid with headers into `reports/powerbi_values.csv`, as comma-separated values with
   the brackets removed from the headers.

Slices are labeled `total`, `year=YYYY`, `year=2024|client_tier=T` and `month=2024-12`. The script turns
each label into a date window (plus a tier) and recomputes the measure in pandas for that window. It
never reads a Power BI value to compute a pandas one.

## Process Note: How AI Was Used

The brief asks for `01_reconcile_measures.py` to be drafted in **Claude Desktop**, run in VS Code, and
reviewed by **Claude Code** before commit. I chose to depart from that split: the script was **drafted in
Claude Code** (inside VS Code), from a written specification of every measure, slice and tolerance. I
ran it, and Claude Code's `/code-review` then ran as a separate review pass before commit. Its findings
and what I did about them are below.

`02_design_questions.py` (the Part C evidence) was drafted and reviewed the same way. That review
caught two wrong figures in my Part C answers before commit, and both were corrected (see below).

**Part D also stayed in Claude Code** instead of Claude Desktop. The prompt in `claude/dax_session.md`
gives Claude the exported metadata, minus the existing `AUM-Weighted Alpha` and `Alpha Signal`
formulas, plus what metadata can't say. That session had already written the Part A version, so the
draft isn't blind. It takes a different route (the fact table's own `snapshot_date` instead of
`LASTNONBLANK`), and `claude/verification.md` judges it only on evidence: the reconciliation rows, 5 edge
cases, and 14,046 filter contexts compared with the Part A measure.

The DAX measures (Part A) were drafted with Claude Code, which the brief allows ("You may use Claude for
other measures too"). I built each one in Power BI Desktop and checked it against pandas figures before
moving on. The Power BI values were exported by me in DAX query view. The copy in
`reports/powerbi_values.csv` was then compared line by line with a fresh export from the open model, and
all rows were identical. That was 91 rows at first, and 92 after `Ending Clients Display` was added and
I re-exported.

## Claude Code Review Findings

### `01_reconcile_measures.py` (Part B)

| What Claude Code flagged | What I did about it |
|---|---|
| Fact dates were never checked against `dim_date`. A fact row dated outside the calendar would still count in an unfiltered DAX SUM, but the pandas date window would drop it, and the script would blame Power BI | Every snapshot, fee and transaction date must be in `dim_date`; otherwise the script stops (exit 2). Fault test: a fee dated 2025-01-01 fails |
| A failed run left the previous `measure_reconciliation.csv` (all matched) in `reports/`, looking current | The report is deleted at the start of every run. Fault test: a stale file is gone after a failed run |
| `nlargest(10)` always keeps exactly 10 clients, but DAX `TOPN` keeps every row tied at the cutoff | `nlargest(10, keep="all")`. Unit test: a tie at rank 10 sums 11 clients, as TOPN does |
| DAX text comparison ignores case (`txn_type = "Deposit"` also matches `deposit`), but pandas compared case-sensitively | `txn_type` is case-folded before filtering. Fault test: 500 deposits relabeled `deposit` still match Power BI |
| Alpha Signal is compared exactly, but it is a threshold on a float, so float noise at ±2% could flip the label | **Kept by choice:** the brief requires every row to match, and a label is either right or wrong. The script now prints how close any alpha comes to ±2%: the closest is 0.0023 away, 23 times the alpha tolerance, so no label is near the boundary |
| `shift()` always snapped the shifted end to a month end, which is wrong for a window ending mid-month, and the code comment's example was wrong | The snap applies only when the window ends on a month end (Nov 1–30 shifts to Oct 1–31; a window ending Dec 15 shifts to Nov 15). Comment corrected. Unit tests cover all three cases |
| Fee and transaction `amount` weren't checked for blanks or text, so a SUM could become 0 (DAX: BLANK) or fail outside the error path | All summed columns must be present and numeric (exit 2 otherwise). Fault test: one blank fee amount fails |
| A bad `dim_date` date or a missing CSV crashed with a raw traceback and exit 1, the code used for "mismatch" | Both raise `ReconcileError` (exit 2) |
| `fee_yield_bps` and `avg_monthly_aum` repeated the naive-SUM expression; the measure lookup table was rebuilt on every call | Both call `naive_sum()`; the lookup table is built once, and the script checks that it covers every measure |
| Slice filters are recomputed many times over the 130k-row snapshot table | **Not changed:** the whole run takes about 2 seconds, so caching would add code without a practical gain |
| **Outcome** | 8 fixed, 2 kept with reasons. 91 of 91 rows still matched (92 of 92 after `Ending Clients Display` was added). 11 fault tests on edited Power BI values (wrong value, wrong label, blank vs number, missing or duplicate row, unknown measure or slice) and 6 tests on the fixes all behave as expected |

### `02_design_questions.py` (Part C evidence)

| What Claude Code flagged | What I did about it |
|---|---|
| The figure labeled "average of the 12 monthly alphas" pooled every 2024 row into one weighted alpha. It was not the average of the 12 monthly values | **A wrong figure in Part C (c).** Now the true mean of the 12 monthly values: 0.30%, not 0.32%. Part C now says it understates the year almost 5 times (4.86), not 4.5 |
| "First month" was each client's first snapshot in the data, so every client who joined before 2020 counted January 2020 as an onboarding month | **A wrong claim in Part C (b).** Onboarding is now the month of `client_since`: 72 of 968 onboarding months are unbilled (7.4% vs 5.7% overall), and they are 1% of all unbilled months. The text was rewritten to match |
| Several figures quoted in Part C (26,216 matched months, 129,547 account-months, 3,875 suspect rows, "no zero-amount fees", "every tier, account type, risk profile, year", 1.45% December alpha, the understatement ratio, "neither Alpha Signal changes") weren't computed or pinned | All are computed and pinned. The figure count went from 59 to 79, and the script fails on any figure it computes but doesn't pin |
| `txn_type` compared case-sensitively, unlike DAX and `01` | Case-folded, as in `01` |
| `is_return_suspect`, `aum`, `amount`, `active_alpha_ytd` not validated, so a blank could silently skew the with/without-suspect comparison | Checked numeric and present; flag must be 0/1 (exit 2 otherwise) |
| The report was written before the pinned-figure check, so a failing run replaced the evidence file with unconfirmed values | Old report deleted at start; new one written only when all 79 figures are confirmed. Fault test: a changed figure fails and no file is left |
| January alpha taken with `iloc[0]` (assumes January exists and is first), with a tolerance half the size of the value | Looked up by date (`2024-01-01`), the script requires 12 months, and the tolerance is 1e-6 |
| `difference` and `departed_clients_last_balance` pinned separately but never compared | Explicit check that they are equal to within half a cent |
| Loader and measure formulas duplicate `01_reconcile_measures.py` | **Kept by choice:** this script needs columns `01` doesn't load (`aum_basis`, `account_type`, `client_since`, `risk_profile`). `01`'s validation rules were copied in instead (numeric, flag, case, dates) |
| Row-by-row Python membership tests over 130k rows, written twice | One vectorized `MultiIndex.isin` helper |
| **Outcome** | 9 fixed (two of them corrected wrong figures in Part C), 1 kept with a reason. 79 figures confirmed. 3 fault tests (changed figure, unpinned figure, no file on failure) pass |

## Reconciliation Mismatches and Fixes

None. All 92 rows (17 measures across 10 slices, covering every slice the brief requires) match. The
first run had 91 rows, and all matched. The 92nd is `Ending Clients Display` at the grand total, added
later as the card workaround. It matched as soon as it was added: "2,325" in both tools. The largest
differences are floating-point noise: $0.0000916 on the naive SUM, $0.000002 on the AUM balances, and
under 1e-12 on every ratio. `AUM (naive SUM)` matches too: both tools show $566.68B at the grand total,
44.5 times the real Ending AUM of $12.73B.

## Status

- [x] Part A — Measure library and Measures report page
- [x] Part B — Reconciliation
- [x] Part C — Design questions
- [x] Part D — Claude-assisted measure (`AUM-Weighted Alpha`)
