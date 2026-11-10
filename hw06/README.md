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
│   └── 01_reconcile_measures.py    ← Part B: independent pandas recompute vs Power BI values
├── reports/
│   ├── powerbi_values.csv          ← Part B input: measure, slice, value (exported from DAX query view)
│   └── measure_reconciliation.csv  ← Part B output: one row per measure × slice, with match flag
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

- **Measures:** 16 in `_Measures`: `Total Fees` and `Net Flows` from the ICEs, `AUM (naive SUM)` (kept
  only to show the mistake), and measures 1–11 with their LY/PM companions. DAX, pattern and meaning for
  each are in `powerbi/measures.md`.
- **Formats:** currency with 2 decimals, percentages with 2 decimals, `Fee Yield (bps)` as a decimal with
  2 decimals, `Ending Clients` as a whole number, `Alpha Signal` as text.
- **Measures page:** cards for Ending AUM, Ending Clients, Avg AUM per Client and Top 10 Client Share; a
  table by `dim_date[year]`; and a table by `dim_client[client_tier]` with a visual-level filter
  `dim_date[year]` = 2024. The file is saved with this page open.

## How to Run

From the repository root, with the course virtual environment active:

```
python hw06/scripts/01_reconcile_measures.py
```

It takes about 2 seconds. Exit code 0 means every row matches, 1 means at least one mismatch (listed on
screen), and 2 means bad input, such as a missing required slice, an unknown measure, or a fact date
outside `dim_date`. On exit 2 no report is written, and any previous report is deleted first so a stale
"all match" file can't be mistaken for the current result.

**Refreshing `reports/powerbi_values.csv`.** The Power BI side comes from Power BI itself:

1. In Power BI Desktop, open `powerbi/hw06.pbix` and go to **DAX query view**.
2. Paste in `powerbi/export_powerbi_values.dax` and run it. It returns 91 rows (`measure, slice, value`)
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

The DAX measures (Part A) were drafted with Claude Code, which the brief allows ("You may use Claude for
other measures too"). I built each one in Power BI Desktop and checked it against pandas figures before
moving on. The Power BI values were exported by me in DAX query view. The copy in
`reports/powerbi_values.csv` was then compared line by line with a fresh export from the open model, and
all 91 rows were identical.

## Claude Code Review Findings

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
| **Outcome** | 8 fixed, 2 kept with reasons. 91 of 91 rows still match. 11 fault tests on edited Power BI values (wrong value, wrong label, blank vs number, missing or duplicate row, unknown measure or slice) and 6 tests on the fixes all behave as expected |

## Reconciliation Mismatches and Fixes

None. All 91 rows (16 measures across 10 slices, covering every slice the brief requires) matched on
the first run. The largest
differences are floating-point noise: $0.0000916 on the naive SUM, $0.000002 on the AUM balances, and
under 1e-12 on every ratio. `AUM (naive SUM)` matches too: both tools show $566.68B at the grand total,
44.5 times the real Ending AUM of $12.73B.

## Status

- [x] Part A — Measure library and Measures report page
- [x] Part B — Reconciliation
- [ ] Part C — Design questions
- [ ] Part D — Claude-assisted measure
