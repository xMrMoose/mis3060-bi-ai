# Claude DAX Session: Measure 9, `AUM-Weighted Alpha`

**Workflow:** Draft → Test → Debug → Review (Week 10).
**Tool:** Claude Code, in VS Code, instead of the Claude Desktop the brief names. I chose to keep all of
HW6 in Claude Code; the README's process note covers this.
**Measure chosen:** 9, `AUM-Weighted Alpha`. It combines a last-date filter, a row exclusion and a
weighted iterator, so it has more to verify than measure 11.

**Independence.** The same Claude Code session had already written a Part A version of this measure.
To keep the draft as independent as possible:
- **What the prompt gives:** only the exported metadata, with the `AUM-Weighted Alpha` and
  `Alpha Signal` rows removed from the measure list, plus what metadata cannot say.
- **What the draft must not do:** reuse the Part A formula.

The draft is still not blind. It is therefore judged only on what Power BI and pandas show
(`verification.md`), not on trust.

---

## Prompt

> I'm building a Power BI measure for Wildcat Capital, a wealth manager. Below is my model's metadata,
> exported with INFO.VIEW queries (full results in `model_metadata.md`), and the facts the metadata
> can't show. Please give me:
> 1. a DAX measure for **AUM-Weighted Alpha**, using only the tables and columns listed;
> 2. an explanation of its filter context: what each part sees, at the grand total, on a year row, and
>    in a client-tier table filtered to 2024;
> 3. a DAX test query I can run in DAX query view to check it, including any edge cases you think
>    matter;
> 4. any claims or assumptions I should verify.
>
> **Business definition:** `active_alpha_ytd` weighted by `aum`, at the last snapshot in the current
> filter, excluding `is_return_suspect = 1`.
>
> **What the metadata can't tell you:**
> - `fact_portfolio_snapshot` grain: one row per client per month. `snapshot_date` is always the 1st of
>   the month, every snapshot date exists in `dim_date[date]`, and a client has at most one row per date.
>   Data runs January 2020 to December 2024.
> - `aum` is a **balance** (semi-additive): sum it across clients on one date, never across months.
> - `active_alpha_ytd` is a **year-to-date** rate stored as a decimal (0.02 = 2%). It resets each
>   January and accumulates, so only the last snapshot in a period holds the full period. Never sum or
>   average it across months.
> - `is_return_suspect` is 0/1; 1 = return flagged as unreliable (some flagged alphas are in the
>   thousands of percent).
> - `dim_date` is marked as the date table on `date`.
>
> **Columns** (from `INFO.VIEW.COLUMNS`, hidden Auto date/time tables omitted):
> - `fact_portfolio_snapshot`: snapshot_id, client_id, advisor_id, benchmark_id, snapshot_date (Date),
>   Year, Month, aum (Number), return_ytd, benchmark_return_ytd, active_alpha_ytd (Number), cash_pct,
>   account_type, is_return_suspect (Integer)
> - `fact_fees`: fee_id, client_id, advisor_id, fee_date, fee_type, aum_basis, bps_charged, amount
> - `fact_transactions`: txn_id, client_id, advisor_id, security_id, txn_date, txn_type, shares, price,
>   amount, is_post_departure_txn
> - `dim_date`: date_id, Date, Year, Quarter, Month, month_name, week_of_year, day_of_week,
>   is_month_end, is_quarter_end, is_year_end, is_trading_day
> - `dim_client`: client_id, first_name, last_name, age, city, state, zip_code, risk_profile,
>   client_tier, primary_account_type, initial_aum, client_since, advisor_id, is_active (True/False)
> - `dim_advisor`, `dim_benchmark`, `dim_security`: keys and descriptive columns
> - `_Measures`: measure table
>
> **Relationships** (from `INFO.VIEW.RELATIONSHIPS`; all many-to-one, single direction, active):
> `fact_portfolio_snapshot` → `dim_client` (client_id), `dim_advisor` (advisor_id), `dim_benchmark`
> (benchmark_id), `dim_date` (snapshot_date → date). `fact_fees` → `dim_client`, `dim_advisor`,
> `dim_date` (fee_date → date). `fact_transactions` → `dim_client`, `dim_advisor`, `dim_security`,
> `dim_date` (txn_date → date). `dim_security` → `dim_benchmark`.
>
> **Existing measures** (from `INFO.VIEW.MEASURES`, all Valid): `Total Fees`, `Net Flows`,
> `AUM (naive SUM)`, `Ending AUM`, `Ending Clients`, `Avg AUM per Client`, `Ending AUM LY`,
> `AUM YoY %`, `Ending AUM PM`, `AUM MoM %`, `Avg Monthly AUM`, `Fee Yield (bps)`,
> `Organic Growth Rate`, `Top 10 Client Share`. For example:
> ```DAX
> Ending AUM =
> CALCULATE (
>     SUM ( fact_portfolio_snapshot[aum] ),
>     LASTNONBLANK ( dim_date[date], CALCULATE ( COUNTROWS ( fact_portfolio_snapshot ) ) )
> )
> ```

---

## Claude's response

### 1. The measure

```DAX
AUM-Weighted Alpha =
VAR LastSnapshotDate =
    MAX ( fact_portfolio_snapshot[snapshot_date] )
VAR LastSnapshotRows =
    CALCULATETABLE (
        fact_portfolio_snapshot,
        fact_portfolio_snapshot[snapshot_date] = LastSnapshotDate,
        fact_portfolio_snapshot[is_return_suspect] = 0
    )
RETURN
    DIVIDE (
        SUMX (
            LastSnapshotRows,
            fact_portfolio_snapshot[aum] * fact_portfolio_snapshot[active_alpha_ytd]
        ),
        SUMX ( LastSnapshotRows, fact_portfolio_snapshot[aum] )
    )
```
Format it as a percentage with 2 decimals.

### 2. Filter context, step by step

- **`LastSnapshotDate`** is the latest `snapshot_date` among the snapshot rows the current filter
  allows. Filters on `dim_date`, `dim_client`, `dim_advisor` and `dim_benchmark` reach the fact through
  the relationships. `MAX` reads the fact's own date column, so it can only return a date that actually
  has data. That matters because snapshots fall on the 1st of the month: `MAX ( dim_date[Date] )` would
  return the 31st, which has no rows. Because every snapshot date is in `dim_date`, this is the same date
  `LASTNONBLANK ( dim_date[date], … )` finds in `Ending AUM`, so the two measures describe the same
  snapshot.
- **The suspect filter comes after the date.** `LastSnapshotDate` is fixed before the
  `is_return_suspect = 0` filter applies, so the date always matches `Ending AUM`. If every row on that
  date were suspect, the measure returns BLANK. It does **not** fall back to an earlier month, which
  would silently mix periods.
- **`LastSnapshotRows`** keeps the current filters and adds two more:
  - **Date:** `snapshot_date = LastSnapshotDate` replaces any filter on that one fact column only.
    Filters from `dim_date` stay, and the date is inside them anyway.
  - **Suspects:** `is_return_suspect = 0` removes flagged rows.
  The result is one row per non-suspect account on the last snapshot.
- **`SUMX … / SUMX …`** gives Σ(aum × alpha) ÷ Σ(aum) over those rows. Each account counts in
  proportion to its balance, and the denominator uses the same rows, so the weights sum to 100% after
  the exclusion. `DIVIDE` returns BLANK if no rows remain.

**In practice:**
- **Grand total:** `LastSnapshotDate` = 2024-12-01. The result is the firm's 2024 year-to-date alpha
  over all non-suspect accounts on that date (2,325 accounts minus the suspects). It is **not** alpha
  since 2020: `active_alpha_ytd` resets each January.
- **Year rows (`dim_date[Year]`):** each year resolves to its December 1 snapshot, so each row is that
  year's full-year alpha. 2020 and 2024 work the same way. No time-intelligence function is used, so
  nothing depends on a prior year existing.
- **Tier table filtered to 2024:** the tier filter (through `dim_client`) and the year filter (through
  `dim_date`) both reach the fact. Each tier uses its own last 2024 snapshot (December 1, if the tier
  has data then) and its own non-suspect accounts. The Total row is the firm value for 2024, not a sum
  or an average of the tier rows.
- **Not additive:** tier rows don't add up to the total, and they shouldn't. Each is a weighted average
  over its own accounts.

### 3. Test query

Run it in DAX query view. It defines the draft under a different name, so it can sit next to anything
already in the model.

```DAX
DEFINE
    MEASURE _Measures[Alpha (draft)] =
        VAR LastSnapshotDate = MAX ( fact_portfolio_snapshot[snapshot_date] )
        VAR LastSnapshotRows =
            CALCULATETABLE (
                fact_portfolio_snapshot,
                fact_portfolio_snapshot[snapshot_date] = LastSnapshotDate,
                fact_portfolio_snapshot[is_return_suspect] = 0
            )
        RETURN
            DIVIDE (
                SUMX ( LastSnapshotRows, fact_portfolio_snapshot[aum] * fact_portfolio_snapshot[active_alpha_ytd] ),
                SUMX ( LastSnapshotRows, fact_portfolio_snapshot[aum] )
            )
    MEASURE _Measures[Last snapshot] = MAX ( fact_portfolio_snapshot[snapshot_date] )
    MEASURE _Measures[Rows on last snapshot] =
        VAR d = MAX ( fact_portfolio_snapshot[snapshot_date] )
        RETURN CALCULATE ( COUNTROWS ( fact_portfolio_snapshot ), fact_portfolio_snapshot[snapshot_date] = d )
    MEASURE _Measures[Rows weighted] =
        VAR d = MAX ( fact_portfolio_snapshot[snapshot_date] )
        RETURN CALCULATE (
            COUNTROWS ( fact_portfolio_snapshot ),
            fact_portfolio_snapshot[snapshot_date] = d,
            fact_portfolio_snapshot[is_return_suspect] = 0
        )

// A. Grand total
EVALUATE
ROW (
    "Last snapshot", [Last snapshot],
    "Rows on last snapshot", [Rows on last snapshot],
    "Rows weighted", [Rows weighted],
    "Alpha (draft)", [Alpha (draft)]
)

// B. By year
EVALUATE
SUMMARIZECOLUMNS (
    dim_date[Year],
    "Last snapshot", [Last snapshot],
    "Rows weighted", [Rows weighted],
    "Alpha (draft)", [Alpha (draft)]
)
ORDER BY dim_date[Year]

// C. By client tier, 2024
EVALUATE
CALCULATETABLE (
    SUMMARIZECOLUMNS (
        dim_client[client_tier],
        "Rows on last snapshot", [Rows on last snapshot],
        "Rows weighted", [Rows weighted],
        "Alpha (draft)", [Alpha (draft)]
    ),
    dim_date[Year] = 2024
)
ORDER BY dim_client[client_tier]

// D. Edge case: clients whose last snapshot is suspect. Expect BLANK, not an earlier month's alpha.
EVALUATE
TOPN (
    5,
    FILTER (
        ADDCOLUMNS (
            VALUES ( dim_client[client_id] ),
            "Last snapshot", [Last snapshot],
            "Rows weighted", [Rows weighted],
            "Alpha (draft)", [Alpha (draft)]
        ),
        [Rows weighted] = 0
    ),
    dim_client[client_id], ASC
)
```

**What to look for:**
- **A:** last snapshot 2024-12-01, and "Rows weighted" below "Rows on last snapshot" by the number of
  suspect accounts.
- **B:** each year's last snapshot is December 1, and alpha is never absurdly large (no suspects).
- **C:** Retail is the tier where weighted rows are fewer than rows, if suspects sit in Retail.
- **D:** BLANK alpha for each client listed.

### 4. Claims and assumptions to verify

1. `MAX ( fact_portfolio_snapshot[snapshot_date] )` finds the same date as
   `LASTNONBLANK ( dim_date[date], … )` in every filter context here, because every snapshot date
   exists in `dim_date`. So this measure and `Ending AUM` always describe the same snapshot.
2. At the grand total, the weighted rows are the accounts on the 2024-12-01 snapshot minus the suspect
   ones.
3. If all of a context's last-date rows are suspect, the result is BLANK, not a fallback to an
   earlier month.
4. On a year row, the result is that year's December 1 snapshot alpha.
5. The measure doesn't rely on `dim_date` being marked as a date table, since it uses no
   time-intelligence functions.

Check the results against an independent calculation (for example, pandas: last `snapshot_date` in
the slice, drop `is_return_suspect == 1`, then `sum(aum * alpha) / sum(aum)`) before trusting it.
