# Specification: Wildcat Capital Transaction EDA Script

## Purpose

I need one single Python script that performs a complete exploratory data
analysis of Wildcat Capital's client transaction history. The script should
load the raw transaction data, validate that it loaded correctly, describe
its structure and quality, characterize the key numeric distributions and
relationships between variables, and save both a text summary and three
charts — all in one run, without requiring any manual steps in between.

## Data

The source file is `data/raw/fact_transactions.csv`. It contains one row per
transaction (Buy, Sell, Deposit, Withdrawal, Dividend, or Advisory Fee) with
these columns: `txn_id`, `client_id`, `advisor_id`, `security_id`,
`txn_date`, `txn_type`, `shares`, `price`, `amount`.

## Requirements

Please write one Python script that does all of the following, in this
order, in a single execution:

1. Loads `data/raw/fact_transactions.csv` into a pandas DataFrame.
2. Prints the shape of the DataFrame (number of rows and columns).
3. Prints every column name along with its data type.
4. Prints the count of missing (null) values for every column.
5. Prints descriptive statistics — count, mean, standard deviation, minimum,
   25th percentile, median, 75th percentile, and maximum — for all numeric
   columns.
6. Prints the value counts and percentages for the `txn_type` column,
   sorted from most frequent to least frequent.
7. Prints the number of unique clients, unique advisors, and unique
   securities referenced anywhere in the file.
8. Prints the earliest and latest transaction date found in `txn_date`
   (the overall date range covered by the dataset).
9. Checks whether any `txn_id` value appears more than once and prints the
   number of duplicate rows found.
10. Prints the mean, median, and skewness of the `amount` column.
11. Groups the transactions by `txn_type` and, for each type, prints the
    count of transactions along with the mean and median `amount` (rounded
    to two decimal places), sorted from highest mean amount to lowest.
12. Computes the correlation matrix between `shares`, `price`, and `amount`
    (rounded to two decimal places), prints the matrix, and separately
    identifies and prints the three strongest correlations among those
    variables, excluding each variable's correlation with itself.
13. Prints the minimum, maximum, and count of negative values found in the
    `shares` column, broken out separately for each `txn_type`.
14. Prints a warning message if the DataFrame's shape is not exactly
    298,772 rows by 9 columns.
15. Creates and saves three charts as PNG files:
    - A histogram of the `amount` column, with vertical lines marking the
      mean and the median, each clearly labeled. Save it to
      `hw02/charts/hist_amount.png`.
    - A horizontal box plot of `amount` grouped by `txn_type`. Save it to
      `hw02/charts/box_amount_by_type.png`.
    - A scatter plot with `shares` on the x-axis and `amount` on the
      y-axis, with points colored by `txn_type`. Save it to
      `hw02/charts/scatter_shares_amount.png`.
16. Saves a plain-text summary containing everything printed in steps 2
    through 13 to a file at `hw02/hw02_profile.txt`.
17. Includes a comment block at the very top of the script identifying the
    script's purpose, the dataset it analyzes, the author, and the date it
    was generated.

## Important constraints

- This must be **one single Python script** that runs start to finish in
  one execution — not separate scripts for each step.
- The script should run cleanly from the command line with no manual
  intervention (for example, no interactive chart windows that block
  execution — charts should save directly to file).
- Use clear, readable print statements with labels, so the terminal output
  is easy to follow without needing to read the code alongside it.
