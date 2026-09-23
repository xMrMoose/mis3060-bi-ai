# HW2 Validation Record

## 2A — Known-Answer Benchmarks

| Check | Expected | Your Script Produced | Match? | Notes |
|---|---|---|---|---|
| Dataset shape | (298772, 9) | (298772, 9) | Yes | |
| Null count — `security_id` | 101,597 | 101,597 | Yes | |
| Null count — `amount` | 0 | 0 | Yes | |
| Unique `txn_type` values | 6 | 6 | Yes | Buy, Sell, Dividend, Deposit, Advisory Fee, Withdrawal |
| Count of `Buy` transactions | 83,556 | 83,556 | Yes | |
| `txn_date` data type | object | str | No | See discrepancy note 1 below |
| Earliest `txn_date` | 2020-01-01 | 2020-01-01 | Yes | |
| Latest `txn_date` | 2024-12-30 | 2024-12-30 | Yes | |
| Duplicate `txn_id` count | 0 | 0 | Yes | |
| Mean `amount` | $54,075.17 | $54,075.17 | Yes | |
| Median `amount` | $41,220.48 | $41,220.49 | No | See discrepancy note 2 below |
| Skewness of `amount` | 1.15 | 1.15 | Yes | |
| Correlation `shares`–`amount` | 0.65 | 0.65 | Yes | |
| Correlation `price`–`amount` | 0.64 | 0.64 | Yes | |
| Correlation `shares`–`price` | 0.00 | 0.00 | Yes | |
| Negative `shares` count (Buy only) | 836 | 836 | Yes | All 836 negative-share rows are `Buy` transactions; other types show 0 |
| Profile file created | Yes | Yes | Yes | `hw02/hw02_profile.txt`, 4,847 bytes |
| Chart files created (3) | Yes | Yes | Yes | `hist_amount.png`, `box_amount_by_type.png`, `scatter_shares_amount.png` all present in `hw02/charts/` |

Grouping benchmark (mean `amount` by `txn_type`) also matched exactly, to the penny, for every type and both count and median:

| `txn_type` | Count | Mean `amount` | Median `amount` | Match? |
|---|---|---|---|---|
| Dividend | 53,864 | $64,077.30 | $48,805.60 | Yes |
| Buy | 83,556 | $63,738.49 | $47,893.58 | Yes |
| Sell | 59,755 | $63,635.55 | $48,080.16 | Yes |
| Deposit | 35,981 | $50,588.07 | $50,760.33 | Yes |
| Withdrawal | 29,850 | $49,997.34 | $49,843.42 | Yes |
| Advisory Fee | 35,766 | $7,375.17 | $859.12 | Yes |

### Discrepancy investigation

**Note 1 — `txn_date` dtype shows `str` instead of `object`.**

I investigated this directly with Claude Code rather than a separate benchmark reference, since it's an environment question, not a data question. The environment is running **pandas 3.0.6**, a very recent release. Pandas 3.0 changed how it stores text columns internally: instead of labeling them with the old generic `object` dtype, it now uses a dedicated `str` dtype by default. My guess is the benchmark was generated on an older pandas version, where the same string-typed column would print as `object`.

The underlying fact the benchmark is actually testing — "is `txn_date` stored as text rather than a real date type?" — is still true: `txn_date` is not parsed as a datetime, and date arithmetic (like subtracting two dates) will not work on it without an explicit conversion. Confirmed by running `df['txn_date'].dtype` directly, which returned `str`, and `pd.__version__`, which returned `3.0.6`. This is a pandas-version labeling difference, not a data quality issue or a script bug.

**Note 2 — Median `amount` is $41,220.49, benchmark says $41,220.48.**

I investigated this by checking the exact underlying float value with Claude Code:

```
>>> df['amount'].median()
np.float64(41220.485)
>>> decimal.Decimal(df['amount'].median())
Decimal('41220.485000000000582076609134674072265625')
```

The true median value lands exactly on a rounding boundary: $41,220.485. This is a genuine 50/50 tie between rounding to $41,220.48 and $41,220.49 — different tools break this tie differently (Python's float formatting rounds this particular tie up to `.49`; my guess is whatever tool produced the official benchmark rounded it down to `.48`). This is a one-cent floating-point rounding-convention difference on an exact halfway value, not an error in the data, the calculation, or the script — both values are defensible depending on the rounding rule applied.

## 2B — Explain the Code and Output

*New Claude Code session used for both prompts, as required.*

**1. Did Claude's predicted outputs (Prompt 1) match what I actually saw in the terminal? List discrepancies.**

Yes — a full match, with no discrepancies. Every value Claude predicted matched the actual terminal output exactly: shape, dtypes, null counts, `describe()` stats, `txn_type` counts/percentages, unique entity counts, date range, duplicate count, mean/median/skew, the grouped table, the correlation matrix and top-3 pairs, and the shares-by-type table. No shape warning appeared, as predicted, since the shape matched `EXPECTED_SHAPE`. The final two confirmation lines ("Charts saved to..." and "Profile summary saved to...") also appeared exactly as predicted.

**2. What did Claude flag as potentially unexpected or worth investigating (Prompt 2)?**

- **836 negative `shares` values, all on `Buy` transactions** (as low as -499.63) — flagged as the most concrete anomaly, since a "Buy" logically shouldn't have negative shares.
- **Advisory Fee's mean ($7,375.17) vs. median ($859.12)** — an 8.6x gap, far larger than any other transaction type, implying a small number of unusually large fee transactions are pulling the average up.
- **`client_id` max (3,192) vs. unique client count (2,700)** — a gap of ~492 IDs, meaning client IDs aren't contiguous and some IDs in that range never transact in this file.
- **Suspiciously round, uniform bounds** on `price` ($10.00–$500.00 exactly) and `shares` (capping near 500 across every type) — a pattern more consistent with simulated/generated data than real market data.

**3. Did Claude mention the 101,597 null values in `security_id`? What explanation did it give?**

Yes. Claude noted that `security_id`, `shares`, and `price` are all null in exactly the same 101,597 rows, and connected that to the `txn_type` breakdown: `Deposit`, `Withdrawal`, and `Advisory Fee` are cash-based transaction types that don't reference a security, so it makes business sense for those fields to be empty on those rows. Claude called this a structural, intentional null pattern tied to `txn_type` — explicitly **not** a data quality problem.

**4. Did Claude flag the `txn_date` column as a concern? Why would that matter for a time-series analysis?**

No — in the Prompt 2 response, Claude reported `txn_date`'s string type as part of the dtype listing in Prompt 1, but did not list it among the things worth investigating in Prompt 2. That's a real gap: because `txn_date` is stored as text rather than a datetime, it can't be used directly for date arithmetic — computing days between transactions, resampling by month/quarter, extracting `.dt.year`/`.dt.month`, or building rolling windows would all fail or behave incorrectly until the column is explicitly converted with `pd.to_datetime()`. It happens to sort correctly as plain text only because the dates are in zero-padded ISO format (`YYYY-MM-DD`), which is a lucky coincidence, not something to rely on. None of the 17 script items in this assignment actually do date arithmetic, so the script runs fine as-is — but the moment someone builds a trend or time-series view on this table, this would need to be fixed first.

**5. Do the chart images match Claude's explanation of that section of the output? Note any differences.**

- **`hist_amount.png`** — matches exactly: a sharp spike near $0 that quickly tapers into a long right tail out past $200K, with the red mean line sitting visibly to the right of the green median line, consistent with the 1.15 right-skew value.
- **`box_amount_by_type.png`** — mostly matches, but the image is more dramatic than the text summary suggested. It does confirm the Advisory Fee anomaly: a tiny compressed box near zero with a dense mass of "outlier" points stretching out to ~$140K. But `Buy`, `Sell`, and `Dividend` each show *so many* points beyond their whiskers that they look like near-solid black bars from ~$100K to $250K — far more than a classic IQR outlier count. The written explanation described this as "moderate skew," but the chart makes clear just how heavy that right tail actually is for the trade-related transaction types.
- **`scatter_shares_amount.png`** — this one adds a finding the text explanation didn't fully capture. Only `Buy` (teal) is visibly plotted at any real density — `Dividend`, `Deposit`, `Withdrawal`, and `Advisory Fee` never appear at all because they have null `shares` and can't be placed on the x-axis, and `Sell` is present but almost entirely hidden underneath the much denser `Buy` layer. More importantly, the negative-share `Buy` transactions (shares from -500 to 0) form a clear mirror-image triangle with **positive** dollar amounts that scale the same way as the ordinary positive-share `Buy` transactions. In other words, `amount` stayed positive even when `shares` went negative — a visual clue that whatever caused the sign flip likely affected only the `shares` field, not `amount`, which is useful context for the negative-shares investigation in 2C.

**6. Follow-up question and Claude's answer.**

> *Question asked: "in the rows where security id, shares and price are null is there any way the amounts are skewed comapred to the rest of the data. are these amoutns typically larger, smaller on average than the other amounts."*

**Answer:** Yes — the null-group amounts are meaningfully smaller than the rest of the data, not larger. Splitting `fact_transactions.csv` into the 101,597 rows where `security_id`/`shares`/`price` are null (`Deposit`, `Withdrawal`, `Advisory Fee`) versus the 197,175 rows where they're populated (`Buy`, `Sell`, `Dividend`):

| | Null rows (no security) | Non-null rows (has security) |
|---|---|---|
| Count | 101,597 | 197,175 |
| Mean `amount` | $35,201.93 | $63,799.85 |
| Median `amount` | $27,404.65 | $48,217.48 |
| Std dev | $32,902.44 | $55,022.94 |
| Max | $142,855.43 | $249,302.33 |

The null-security rows average about 45% lower than the non-null rows on both mean and median, and their maximum tops out far lower too (~$143K vs ~$249K) — consistent with the box plot, where `Buy`/`Sell`/`Dividend` show a long right tail of very large transactions that `Deposit`/`Withdrawal`/`Advisory Fee` don't have. The skew is driven mostly by `Advisory Fee`, whose own median is just $859.12 — it pulls the whole null-group average down even though `Deposit` and `Withdrawal` individually sit close to the overall dataset mean (~$50K each) on their own. So it isn't that "null rows" behave oddly as a category — it's that one specific cash transaction type (fees) is small and numerous, and it happens to share the same null pattern as two normal-sized ones (deposits/withdrawals).
