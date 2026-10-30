# common.py
# Shared helpers for the HW5 scripts: paths, table loading, blank and type
# tests, and a check collector that runs every check before failing.
# Author: Jonah Karst
# Generated: 2026-10-30

from pathlib import Path

import pandas as pd

HW_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = HW_DIR / "data" / "clean"
REPORTS_DIR = HW_DIR / "reports"

TABLES = ["dim_advisor", "dim_benchmark", "dim_client", "dim_date", "dim_security",
          "fact_fees", "fact_portfolio_snapshot", "fact_transactions"]

# Canonical whole number: ASCII digits, no sign, no leading zero, fits Int64.
# '07' would pass a plain \d+ test but collide with '7' once Power BI casts it.
WHOLE_NUMBER = r"0|[1-9][0-9]{0,17}"


def load_tables(names=TABLES):
    """Read each clean table as text, so every type conversion is explicit."""
    return {name: pd.read_csv(DATA_DIR / f"{name}.csv", dtype=str, keep_default_na=False)
            for name in names}


def is_blank(series):
    return series.str.strip().eq("")


def is_whole_number(series):
    return bool(series.str.fullmatch(WHOLE_NUMBER).all())


def parse_iso_date(series):
    return pd.to_datetime(series, format="%Y-%m-%d", errors="coerce")


def is_iso_date(series):
    return bool(parse_iso_date(series).notna().all())


class Checks:
    """Collect failed checks so every check runs and reports are written before raising."""

    def __init__(self, error_class):
        self.error_class = error_class
        self.failures = []

    def __call__(self, condition, message):
        if not condition:
            self.failures.append(message)
            print(f"   FAIL: {message}")

    def raise_if_failed(self):
        if self.failures:
            raise self.error_class(f"{len(self.failures)} check(s) failed: " + "; ".join(self.failures))
