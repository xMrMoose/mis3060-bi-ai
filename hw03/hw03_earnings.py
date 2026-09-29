"""
hw03_earnings.py

Purpose:     Pull the four most recent quarterly earnings press releases
             (SEC Form 8-K, Item 2.02) for five public companies from SEC
             EDGAR, extract period / revenue / diluted EPS / net income from
             the press-release text, and save the results to a CSV.
Data source: SEC EDGAR submissions API
             (https://data.sec.gov/submissions/CIK{cik}.json) and the
             EX-99.1 press-release exhibit of each Item 2.02 filing.
Output:      hw03/earnings_history.csv
Author:      Jonah Karst
Generated:   2026-09-29

Run from the command line:
    python hw03/hw03_earnings.py

Units: revenue_reported and net_income are always millions of US dollars
(plain numbers). eps_diluted is dollars per share. Any field that cannot
be extracted is stored as the string "NOT_FOUND".
"""

import csv
import re
import sys
import time
from decimal import Decimal
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# Press releases contain characters (dashes, curly quotes) that the default
# Windows console encoding cannot print, so force UTF-8 output.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
HEADERS = {"User-Agent": "MIS3060 Villanova jkarst@villanova.edu"}
REQUEST_TIMEOUT = 30          # seconds, applied to every request
REQUEST_PAUSE = 0.2           # seconds between requests (SEC limit: 10/sec)
RETRY_PAUSE = 2               # seconds before the single retry
FILINGS_PER_COMPANY = 4
MAX_EXTRA_EXHIBITS = 2        # other EX-99.x exhibits to try for missing fields
NOT_FOUND = "NOT_FOUND"

COMPANIES = [
    {"company": "Apple Inc.", "ticker": "AAPL", "cik": "0000320193"},
    {"company": "Microsoft Corporation", "ticker": "MSFT", "cik": "0000789019"},
    {"company": "NVIDIA Corporation", "ticker": "NVDA", "cik": "0001045810"},
    {"company": "JPMorgan Chase & Co.", "ticker": "JPM", "cik": "0000019617"},
    {"company": "Walmart Inc.", "ticker": "WMT", "cik": "0000104169"},
]

SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
ARCHIVE_ROOT = "https://www.sec.gov"
FILING_FOLDER = ARCHIVE_ROOT + "/Archives/edgar/data/{cik_int}/{acc_nodash}/"

OUTPUT_PATH = Path(__file__).resolve().parent / "earnings_history.csv"
CSV_COLUMNS = [
    "company", "ticker", "cik", "filing_date",
    "period", "revenue_reported", "eps_diluted", "net_income",
]

# ---------------------------------------------------------------------------
# Regular expressions (edit these if a company's extraction fails)
# ---------------------------------------------------------------------------
NUM = r"[\d,]+(?:\.\d+)?"                      # 109.4 / 28,000
TABLE_NUM = r"\d{1,3}(?:,\d{3})+(?:\.\d+)?"    # 28,000 (needs a thousands comma)

# Words allowed directly before "revenue" so that segment figures such as
# "Data Center revenue of $89.0 billion" are rejected in favor of the total.
REVENUE_ALLOWED_PREFIX = {
    "", "quarterly", "total", "record", "reported", "net", "consolidated",
    "quarter", "and", "with",
}

# Narrative revenue, e.g. "quarterly revenue of $109.4 billion",
# "Revenue was $90.0 billion", "Total revenues were $180.6 billion".
REVENUE_NARRATIVE = re.compile(
    r"(?P<pre>[A-Za-z&-]+\s+)?(?:net\s+)?(?:revenues?|net\s+sales)\s+"
    r"(?:of|was|were|totaled|reached|came\s+in\s+at|:)\s*\$\s?"
    r"(?P<num>" + NUM + r")\s*(?P<unit>billion|million)",
    re.IGNORECASE,
)

# Income-statement table row, e.g. "Total net revenue 46,012 ..." (unit comes
# from the "(in millions)" style table header).
REVENUE_TABLE = re.compile(
    r"total\s+(?:net\s+)?(?:revenues?|net\s+sales)\s*\$?\s*(?P<num>" + TABLE_NUM + r")",
    re.IGNORECASE,
)

# Any revenue row in a table ("Total revenue 90,007", "Revenue $ 96,200"). Used only
# to replace a rounded prose figure ("$90.0 billion") with the exact table figure
# that agrees with it, never as a source of a new number on its own.
REVENUE_TABLE_ROW = re.compile(
    r"(?:total\s+)?(?:net\s+)?(?:revenues?|net\s+sales)\s*\$?\s*(?P<num>" + TABLE_NUM + r")",
    re.IGNORECASE,
)

# GAAP diluted EPS, tried in order. Each has one capture group: the dollars.
EPS_PATTERNS = [
    # "Diluted earnings per share was $4.81", "diluted EPS of $2.01"
    re.compile(r"diluted\s+(?:net\s+)?(?:earnings|income)\s+per\s+(?:common\s+)?share"
               r"(?:\s+\(EPS\))?(?:\s+attributable\s+to\s+\w+)?\s*(?:was|were|of|is|:|totaled|came\s+in\s+at)?\s*"
               r"(?:GAAP\s+)?\$\s?(\d+\.\d{2})", re.IGNORECASE),
    # "GAAP earnings per diluted share was $2.05"
    re.compile(r"earnings\s+per\s+diluted\s+share(?:\s+\(EPS\))?\s*(?:was|were|of|is|:)?\s*\$\s?(\d+\.\d{2})",
               re.IGNORECASE),
    # "$5.07 per diluted share"
    re.compile(r"\$\s?(\d+\.\d{2})\s+per\s+diluted\s+share", re.IGNORECASE),
    # "diluted EPS of $5.07", "EPS of $5.07"
    re.compile(r"(?:diluted\s+)?\bEPS\s+(?:was|of|:)\s*\$\s?(\d+\.\d{2})", re.IGNORECASE),
    # "or $5.07 per share" (JPMorgan headline states diluted EPS this way)
    re.compile(r"\$\s?(\d+\.\d{2})\s+per\s+share", re.IGNORECASE),
    # Income-statement table row: "Diluted $ 2.01"
    re.compile(r"\bdiluted\b\s*:?\s*\$\s?(\d{1,3}\.\d{2})\b", re.IGNORECASE),
]

# Net income in prose, e.g. "Net income was $35.8 billion",
# "net income attributable to Walmart was $4.6 billion".
NET_INCOME_NARRATIVE = re.compile(
    r"net\s+income(?P<attr>\s+attributable\s+to\s+[\w.&' ]{1,40}?)?\s+"
    r"(?:was|of|were|totaled|:)\s*\$\s?(?P<num>" + NUM + r")\s*(?P<unit>billion|million)",
    re.IGNORECASE,
)

# Net income table rows. The first form prefers "attributable to <company>"
# (Walmart, JPMorgan); the second is the plain "Net income $ 27,466" row.
NET_INCOME_TABLE_ATTRIBUTABLE = re.compile(
    r"net\s+income\s+attributable\s+to\s+(?P<who>[\w.&' ]{1,40}?)\s*\$?\s*(?P<num>" + TABLE_NUM + r")",
    re.IGNORECASE,
)
NET_INCOME_TABLE_PLAIN = re.compile(
    r"\bnet\s+income\s*\$?\s*(?P<num>" + TABLE_NUM + r")",
    re.IGNORECASE,
)

# A "non-GAAP" label sitting immediately before a figure's wording.
NON_GAAP_LABEL = re.compile(
    r"non-?gaap[\s:\-]*(?:(?:diluted|net|total|adjusted|operating|earnings|income|revenues?|per|share|and)\s+)*$",
    re.IGNORECASE,
)

# Unit header of a financial table: "(in millions, except per share data)".
TABLE_UNIT = re.compile(r"\(\s*(?:dollars\s+)?in\s+(millions|thousands|billions)\b", re.IGNORECASE)
# Fallback for headers written without a parenthesis ("In millions").
# Only used if no "(in ...)" header is found; the strict form above matters
# because Apple's header says "(In millions, except number of shares, which
# are reflected in thousands, ...)" and the dollar unit is the FIRST one.
TABLE_UNIT_LOOSE = re.compile(r"\bin\s+(millions|thousands|billions)\b", re.IGNORECASE)

# Reporting period. Each pattern is tried and the earliest match in the text
# wins (the headline states the current quarter).
ORDINALS = r"(first|second|third|fourth)"
PERIOD_PATTERNS = [
    # "third quarter fiscal 2026", "Second-quarter 2026", "fourth quarter of 2024",
    # "Fourth Quarter and Fiscal Year 2024"
    ("q_year", re.compile(ORDINALS + r"[\s-]+quarter\s+(?:of\s+|and\s+(?:full[-\s]year\s+)?)?"
                          r"(fiscal\s+)?(?:year\s+)?(20\d{2})", re.IGNORECASE)),
    # "fiscal 2026 third quarter"
    ("year_q", re.compile(r"fiscal\s+(?:year\s+)?(20\d{2})\s+" + ORDINALS + r"[\s-]+quarter", re.IGNORECASE)),
    # "third quarter ended June 27, 2026"
    ("q_ended", re.compile(ORDINALS + r"[\s-]+quarter\s+(?:ended|ending)\s+[A-Za-z]+\s+\d{1,2},\s+(20\d{2})",
                           re.IGNORECASE)),
    # "Q2 FY27", "Q3 FY2026"
    ("q_fy", re.compile(r"\bQ([1-4])\s*FY\s*(\d{2,4})\b", re.IGNORECASE)),
    # "FY26 Q4", "Fiscal Year 2027 Q2"
    ("fy_q", re.compile(r"\b(?:FY|fiscal\s+(?:year\s+)?)\s*(\d{2,4})\s*Q([1-4])\b", re.IGNORECASE)),
    # "2Q26" (calendar-year style, e.g. JPMorgan)
    ("nq_yy", re.compile(r"\b([1-4])Q\s?(\d{2})\b")),
]
ORDINAL_BY_NUMBER = {"1": "first", "2": "second", "3": "third", "4": "fourth"}


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------
def http_get(url):
    """GET a URL with the SEC User-Agent, a timeout, a pause, and one retry."""
    last_error = None
    for attempt in (1, 2):
        try:
            response = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            time.sleep(REQUEST_PAUSE)
            return response
        except requests.RequestException as error:
            last_error = error
            if attempt == 1:
                time.sleep(RETRY_PAUSE)
    raise last_error


def html_to_text(html):
    """Strip HTML to plain text with single spaces."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    text = soup.get_text(" ")
    return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()


# ---------------------------------------------------------------------------
# EDGAR navigation
# ---------------------------------------------------------------------------
def get_earnings_filings(cik):
    """Return up to four most recent 8-K filings with Item 2.02, newest first."""
    data = http_get(SUBMISSIONS_URL.format(cik=cik)).json()
    recent = data["filings"]["recent"]
    filings = []
    for form, items, date, accession in zip(
        recent["form"], recent["items"], recent["filingDate"], recent["accessionNumber"]
    ):
        item_list = [item.strip() for item in items.split(",")]
        if form == "8-K" and "2.02" in item_list:
            filings.append({"filing_date": date, "accession": accession})
    filings.sort(key=lambda f: f["filing_date"], reverse=True)
    return filings[:FILINGS_PER_COMPANY]


def find_exhibit_urls(cik, accession):
    """Return the .htm EX-99.x exhibit URLs of a filing, EX-99.1 first."""
    folder = FILING_FOLDER.format(cik_int=int(cik), acc_nodash=accession.replace("-", ""))
    index_html = http_get(folder + accession + "-index.html").text
    soup = BeautifulSoup(index_html, "html.parser")

    primary, others = [], []
    for table in soup.find_all("table", class_="tableFile"):
        for row in table.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) < 4:
                continue
            doc_type = cells[3].get_text(strip=True).upper()
            link = cells[2].find("a")
            if not doc_type.startswith("EX-99") or link is None:
                continue
            href = link.get("href", "")
            if not href.lower().endswith(".htm"):
                continue
            href = href.replace("/ix?doc=", "")
            url = href if href.startswith("http") else ARCHIVE_ROOT + href
            if url in primary or url in others:
                continue
            (primary if doc_type == "EX-99.1" else others).append(url)
    return primary + others


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------
def to_millions(number, unit):
    """Convert a figure with a unit word to millions of USD (float)."""
    value = Decimal(number.replace(",", ""))
    factor = {"billion": 1000, "billions": 1000, "million": 1, "millions": 1,
              "thousand": Decimal("0.001"), "thousands": Decimal("0.001")}
    return float(value * Decimal(factor[unit.lower()]))


def is_non_gaap(text, start):
    """True if the match is directly labeled non-GAAP (e.g. 'non-GAAP diluted ...').

    A bare 'non-GAAP basis' at the end of the previous sentence does not count.
    """
    return bool(NON_GAAP_LABEL.search(text[max(0, start - 60):start]))


def full_year(year):
    """'27' -> '2027'; '2027' stays '2027'."""
    return "20" + year if len(year) == 2 else year


def table_unit_before(text, position):
    """Unit word of the closest table header before position, or None."""
    for pattern in (TABLE_UNIT, TABLE_UNIT_LOOSE):
        unit = None
        for match in pattern.finditer(text, 0, position):
            unit = match.group(1)
        if unit:
            return unit
    return None


def extract_period(text):
    """Earliest-mentioned reporting period, e.g. 'third quarter fiscal 2026'."""
    best = None
    for kind, pattern in PERIOD_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        if kind == "q_year":
            period = f"{match.group(1).lower()} quarter " + ("fiscal " if match.group(2) else "") + match.group(3)
        elif kind == "year_q":
            period = f"{match.group(2).lower()} quarter fiscal {match.group(1)}"
        elif kind == "q_ended":
            period = f"{match.group(1).lower()} quarter {match.group(2)}"
        elif kind == "fy_q":
            period = f"{ORDINAL_BY_NUMBER[match.group(2)]} quarter fiscal {full_year(match.group(1))}"
        elif kind == "nq_yy":
            period = f"{ORDINAL_BY_NUMBER[match.group(1)]} quarter {full_year(match.group(2))}"
        else:  # q_fy
            period = f"{ORDINAL_BY_NUMBER[match.group(1)]} quarter fiscal {full_year(match.group(2))}"
        if best is None or match.start() < best[0]:
            best = (match.start(), period)
    return best[1] if best else NOT_FOUND


def rounding_tolerance(number, unit):
    """Half of the last decimal place of a prose figure, in millions of USD.

    "$90.0 billion" is only precise to $0.1 billion, so any true value within
    +/- $50 million (half of 0.1 billion) would be written that way.
    """
    decimals = len(number.split(".")[1]) if "." in number else 0
    half_step = Decimal("0.5") * Decimal(10) ** -decimals
    return to_millions(str(half_step), unit) + 0.001


def exact_from_table(candidates, prose_value, tolerance):
    """First exact table figure that agrees with the rounded prose figure, else None."""
    for value in candidates:
        if abs(value - prose_value) <= tolerance:
            return value
    return None


def revenue_table_candidates(text):
    """Every revenue-row figure in the text, in millions of USD."""
    for match in REVENUE_TABLE_ROW.finditer(text):
        unit = table_unit_before(text, match.start())
        if unit:
            yield to_millions(match.group("num"), unit)


def net_income_table_candidates(text):
    """Every GAAP net income table figure in the text, in millions of USD."""
    for pattern in (NET_INCOME_TABLE_ATTRIBUTABLE, NET_INCOME_TABLE_PLAIN):
        for match in pattern.finditer(text):
            who = (match.groupdict().get("who") or "").lower()
            if "noncontrolling" in who or "non-controlling" in who:
                continue
            unit = table_unit_before(text, match.start())
            if unit:
                yield to_millions(match.group("num"), unit)


def extract_revenue(text):
    """Total quarterly revenue in millions of USD, or None.

    Finds the figure in the prose, then swaps in the exact income-statement table
    figure if one agrees with it within the prose's rounding.
    """
    for match in REVENUE_NARRATIVE.finditer(text):
        prefix = (match.group("pre") or "").strip().lower()
        if prefix in REVENUE_ALLOWED_PREFIX and not is_non_gaap(text, match.start()):
            prose = to_millions(match.group("num"), match.group("unit"))
            exact = exact_from_table(revenue_table_candidates(text), prose,
                                     rounding_tolerance(match.group("num"), match.group("unit")))
            return prose if exact is None else exact
    for match in REVENUE_TABLE.finditer(text):
        unit = table_unit_before(text, match.start())
        if unit:
            return to_millions(match.group("num"), unit)
    return None


def extract_eps(text):
    """GAAP diluted EPS as a string like '4.81', or None."""
    for pattern in EPS_PATTERNS:
        for match in pattern.finditer(text):
            if not is_non_gaap(text, match.start()):
                return match.group(1)
    return None


def extract_net_income(text):
    """GAAP net income in millions of USD, or None."""
    for match in NET_INCOME_NARRATIVE.finditer(text):
        attributable = (match.group("attr") or "").lower()
        if "noncontrolling" in attributable or "non-controlling" in attributable:
            continue
        if not is_non_gaap(text, match.start()):
            prose = to_millions(match.group("num"), match.group("unit"))
            exact = exact_from_table(net_income_table_candidates(text), prose,
                                     rounding_tolerance(match.group("num"), match.group("unit")))
            return prose if exact is None else exact
    for pattern in (NET_INCOME_TABLE_ATTRIBUTABLE, NET_INCOME_TABLE_PLAIN):
        for match in pattern.finditer(text):
            who = (match.groupdict().get("who") or "").lower()
            if "noncontrolling" in who or "non-controlling" in who:
                continue
            unit = table_unit_before(text, match.start())
            if unit:
                return to_millions(match.group("num"), unit)
    return None


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------
def format_millions(value):
    """Console format for a millions figure, e.g. $109,400M."""
    if value == NOT_FOUND:
        return NOT_FOUND
    return f"${value:,.0f}M" if float(value).is_integer() else f"${value:,.1f}M"


def format_eps(value):
    return NOT_FOUND if value == NOT_FOUND else f"${value}"


def print_row(row):
    print(f"{row['ticker']} | {row['period']} | Revenue: {format_millions(row['revenue_reported'])} "
          f"| EPS: {format_eps(row['eps_diluted'])} | Net Income: {format_millions(row['net_income'])}")


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------
def empty_row(company, filing):
    """A row for a filing whose extraction failed entirely."""
    return {
        "company": company["company"], "ticker": company["ticker"], "cik": company["cik"],
        "filing_date": filing["filing_date"], "period": NOT_FOUND,
        "revenue_reported": NOT_FOUND, "eps_diluted": NOT_FOUND, "net_income": NOT_FOUND,
    }


def process_filing(company, filing):
    """Download the press release(s) for one filing and extract one row."""
    row = empty_row(company, filing)
    exhibit_urls = find_exhibit_urls(company["cik"], filing["accession"])
    if not exhibit_urls:
        print(f"  WARNING: {company['ticker']} {filing['filing_date']}: "
              f"no EX-99 press release (.htm) found in filing index")
        return row

    # Main press release first, then up to two other exhibits for missing fields only.
    for position, url in enumerate(exhibit_urls[: 1 + MAX_EXTRA_EXHIBITS]):
        try:
            text = html_to_text(http_get(url).text)
        except Exception as error:
            print(f"  WARNING: {company['ticker']} {filing['filing_date']}: could not download {url} ({error})")
            continue

        if position == 0:
            row["period"] = extract_period(text)
        found = {
            "revenue_reported": extract_revenue(text),
            "eps_diluted": extract_eps(text),
            "net_income": extract_net_income(text),
        }
        for field, value in found.items():
            if row[field] == NOT_FOUND and value is not None:
                row[field] = value

        if all(row[f] != NOT_FOUND for f in ("revenue_reported", "eps_diluted", "net_income")):
            break
    return row


def main():
    rows = []
    for company in COMPANIES:
        print(f"\n=== {company['company']} ({company['ticker']}) ===")
        try:
            filings = get_earnings_filings(company["cik"])
        except Exception as error:
            print(f"  WARNING: {company['ticker']}: could not load filings list ({error}); skipping company")
            continue
        if len(filings) < FILINGS_PER_COMPANY:
            print(f"  NOTE: {company['ticker']}: only {len(filings)} Item 2.02 filing(s) found "
                  f"(expected {FILINGS_PER_COMPANY})")

        for filing in filings:
            try:
                row = process_filing(company, filing)
            except Exception as error:
                print(f"  WARNING: {company['ticker']} {filing['filing_date']}: {error}")
                row = empty_row(company, filing)
            rows.append(row)
            print_row(row)

    with open(OUTPUT_PATH, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    incomplete = sum(
        1 for row in rows
        if any(row[field] == NOT_FOUND for field in CSV_COLUMNS[4:])
    )
    print(f"\nSaved {len(rows)} rows to {OUTPUT_PATH}")
    print(f"Rows with at least one NOT_FOUND: {incomplete}")


if __name__ == "__main__":
    main()
