import pandas as pd

df = pd.read_csv("data/raw/fact_transactions.csv")

buy_count = (df["txn_type"] == "Buy").sum()
print(f"Buy transaction count: {buy_count}")
