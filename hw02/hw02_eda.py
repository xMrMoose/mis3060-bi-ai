# hw02_eda.py
# Exploratory Data Analysis script for Wildcat Capital's client transaction
# history (fact_transactions.csv).
# Author: Jonah Karst
# Generated: 2026-09-22

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

DATA_PATH = "data/raw/fact_transactions.csv"
PROFILE_PATH = "hw02/hw02_profile.txt"
CHARTS_DIR = "hw02/charts"
EXPECTED_SHAPE = (298772, 9)

summary_lines = []


def log(line=""):
    """Print to terminal and record for the saved text profile."""
    print(line)
    summary_lines.append(str(line))


# 1. Load the data
df = pd.read_csv(DATA_PATH)

# 2. Shape
log("=" * 60)
log("2. DATASET SHAPE")
log("=" * 60)
log(f"Rows: {df.shape[0]}, Columns: {df.shape[1]}")
log()

# 3. Column names and data types
log("=" * 60)
log("3. COLUMN NAMES AND DATA TYPES")
log("=" * 60)
log(df.dtypes.to_string())
log()

# 4. Missing values per column
log("=" * 60)
log("4. MISSING VALUES PER COLUMN")
log("=" * 60)
log(df.isnull().sum().to_string())
log()

# 5. Descriptive statistics for numeric columns
log("=" * 60)
log("5. DESCRIPTIVE STATISTICS (NUMERIC COLUMNS)")
log("=" * 60)
log(df.describe().to_string())
log()

# 6. Value counts and percentages for txn_type
log("=" * 60)
log("6. TXN_TYPE VALUE COUNTS AND PERCENTAGES")
log("=" * 60)
txn_counts = df["txn_type"].value_counts()
txn_pcts = df["txn_type"].value_counts(normalize=True) * 100
txn_summary = pd.DataFrame({"count": txn_counts, "pct": txn_pcts.round(2)})
log(txn_summary.to_string())
log()

# 7. Unique counts of clients, advisors, securities
log("=" * 60)
log("7. UNIQUE ENTITY COUNTS")
log("=" * 60)
log(f"Unique clients: {df['client_id'].nunique()}")
log(f"Unique advisors: {df['advisor_id'].nunique()}")
log(f"Unique securities: {df['security_id'].nunique()}")
log()

# 8. Date range
log("=" * 60)
log("8. TXN_DATE RANGE")
log("=" * 60)
log(f"Earliest txn_date: {df['txn_date'].min()}")
log(f"Latest txn_date: {df['txn_date'].max()}")
log()

# 9. Duplicate txn_id check
log("=" * 60)
log("9. DUPLICATE TXN_ID CHECK")
log("=" * 60)
duplicate_count = df["txn_id"].duplicated().sum()
log(f"Duplicate txn_id count: {duplicate_count}")
log()

# 10. Mean, median, skewness of amount
log("=" * 60)
log("10. AMOUNT: MEAN, MEDIAN, SKEWNESS")
log("=" * 60)
amount_mean = df["amount"].mean()
amount_median = df["amount"].median()
amount_skew = df["amount"].skew()
log(f"Mean amount: ${amount_mean:,.2f}")
log(f"Median amount: ${amount_median:,.2f}")
log(f"Skewness of amount: {amount_skew:.2f}")
log()

# 11. Group by txn_type: count, mean, median amount
log("=" * 60)
log("11. AMOUNT BY TXN_TYPE (GROUPED)")
log("=" * 60)
grouped = df.groupby("txn_type")["amount"].agg(
    count="count", mean="mean", median="median"
)
grouped["mean"] = grouped["mean"].round(2)
grouped["median"] = grouped["median"].round(2)
grouped = grouped.sort_values("mean", ascending=False)
log(grouped.to_string())
log()

# 12. Correlation matrix for shares, price, amount
log("=" * 60)
log("12. CORRELATION MATRIX (SHARES, PRICE, AMOUNT)")
log("=" * 60)
corr_matrix = df[["shares", "price", "amount"]].corr().round(2)
log(corr_matrix.to_string())
log()

corr_pairs = (
    corr_matrix.where(~np.eye(len(corr_matrix), dtype=bool))
    .stack()
    .drop_duplicates()
)
top3 = corr_pairs.abs().sort_values(ascending=False).head(3)
log("Three strongest correlations (excluding self-correlation):")
for (var1, var2), _ in top3.items():
    log(f"  {var1} - {var2}: {corr_matrix.loc[var1, var2]}")
log()

# 13. Negative shares by txn_type
log("=" * 60)
log("13. SHARES: MIN, MAX, NEGATIVE COUNT BY TXN_TYPE")
log("=" * 60)
shares_by_type = df.groupby("txn_type")["shares"].agg(
    min_shares="min",
    max_shares="max",
    negative_count=lambda s: (s < 0).sum(),
)
log(shares_by_type.to_string())
log()

# 14. Shape warning
if df.shape != EXPECTED_SHAPE:
    print(
        f"WARNING: Expected shape {EXPECTED_SHAPE}, but got {df.shape}. "
        "Data may be incomplete or corrupted."
    )

# 15. Charts
import os

os.makedirs(CHARTS_DIR, exist_ok=True)

# Histogram of amount with mean/median lines
fig, ax = plt.subplots(figsize=(10, 6))
ax.hist(df["amount"], bins=100, color="#4C72B0", edgecolor="none")
ax.axvline(amount_mean, color="red", linestyle="--", linewidth=2,
           label=f"Mean: ${amount_mean:,.2f}")
ax.axvline(amount_median, color="green", linestyle="--", linewidth=2,
           label=f"Median: ${amount_median:,.2f}")
ax.set_title("Distribution of Transaction Amount")
ax.set_xlabel("Amount ($)")
ax.set_ylabel("Frequency")
ax.legend()
fig.tight_layout()
fig.savefig(f"{CHARTS_DIR}/hist_amount.png", dpi=150)
plt.close(fig)

# Horizontal box plot of amount by txn_type
fig, ax = plt.subplots(figsize=(10, 6))
order = df.groupby("txn_type")["amount"].median().sort_values().index
data_by_type = [df.loc[df["txn_type"] == t, "amount"] for t in order]
ax.boxplot(data_by_type, orientation="horizontal", tick_labels=order)
ax.set_title("Transaction Amount by Type")
ax.set_xlabel("Amount ($)")
ax.set_ylabel("Transaction Type")
fig.tight_layout()
fig.savefig(f"{CHARTS_DIR}/box_amount_by_type.png", dpi=150)
plt.close(fig)

# Scatter plot of shares vs amount colored by txn_type
fig, ax = plt.subplots(figsize=(10, 6))
types = df["txn_type"].unique()
colors = plt.cm.tab10(np.linspace(0, 1, len(types)))
for t, c in zip(types, colors):
    subset = df[df["txn_type"] == t]
    ax.scatter(subset["shares"], subset["amount"], s=5, alpha=0.4,
               color=c, label=t)
ax.set_title("Shares vs. Amount by Transaction Type")
ax.set_xlabel("Shares")
ax.set_ylabel("Amount ($)")
ax.legend(markerscale=3)
fig.tight_layout()
fig.savefig(f"{CHARTS_DIR}/scatter_shares_amount.png", dpi=150)
plt.close(fig)

print(f"Charts saved to {CHARTS_DIR}/")

# 16. Save text summary (items 2-13) to file
with open(PROFILE_PATH, "w") as f:
    f.write("\n".join(summary_lines))

print(f"Profile summary saved to {PROFILE_PATH}")
