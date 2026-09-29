# HW3 Specifications: SEC 8-K Extraction Pipelines

Two independent specifications follow. Each is written to be sent on its own,
as a complete instruction, to Claude Code in a fresh session. The shared
context (companies, header, rules for "NOT_FOUND") is therefore repeated in
both on purpose.

---

# Specification A: Earnings Pipeline (Item 2.02)

## Purpose

I need one single Python script, `hw03/hw03_earnings.py`, that pulls the four
most recent quarterly earnings press releases for each of five public
companies directly from SEC EDGAR, extracts the key financial figures from
the press-release text, and saves them to one CSV. It must run start to
finish in a single execution with no manual steps, and it must never crash
because one filing is hard to parse.

## Data source and companies

The source is the SEC EDGAR submissions API at
`https://data.sec.gov/submissions/CIK{cik}.json`, where `{cik}` is the
10-digit zero-padded CIK exactly as written below. Use these values exactly:

| Company | Ticker | CIK |
|---|---|---|
| Apple Inc. | AAPL | 0000320193 |
| Microsoft Corporation | MSFT | 0000789019 |
| NVIDIA Corporation | NVDA | 0001045810 |
| JPMorgan Chase & Co. | JPM | 0000019617 |
| Walmart Inc. | WMT | 0000104169 |

Required packages are `requests` and `beautifulsoup4` only. Do not use
pandas, lxml, or any package beyond the standard library plus those two
(the standard `csv` module is fine for writing the file).

## Requirements

Please write one Python script that does all of the following, in this
order, in a single execution:

1. Defines the header `{"User-Agent": "MIS3060 Villanova jkarst@villanova.edu"}`
   once and sends it on **every** `requests.get()` call in the script,
   including the submissions API call, every filing-index call, and every
   exhibit download. The simplest way to guarantee this is one small helper
   function that all HTTP requests go through. Set a timeout of 30 seconds
   on every request, and pause 0.2 seconds between requests to stay well
   under the SEC's 10-requests-per-second limit.
2. For each of the five companies, calls the submissions API and reads the
   `filings.recent` arrays (`form`, `items`, `filingDate`,
   `accessionNumber`). Keeps only entries where `form` is exactly `"8-K"`
   and the `items` field, split on commas, contains exactly `"2.02"`
   (Results of Operations and Financial Condition). Do not match on
   substring, and do not include `8-K/A` amendments.
3. Sorts the matching filings newest first and keeps the most recent
   **four** per company (one per quarter). If a company has fewer than four,
   process however many exist and print a note; do not treat this as an
   error.
4. For each selected filing, builds the filing folder URL
   `https://www.sec.gov/Archives/edgar/data/{cik without leading zeros}/{accession number without dashes}/`
   and downloads the filing index page at
   `{folder}{accession number with dashes}-index.html`. Parses the document
   table on that page (the table with class `tableFile`) to find the
   earnings press release exhibit: the row whose **Type** column is
   `EX-99.1` and whose file ends in `.htm`. Do not guess from file names,
   because every company names its exhibits differently and the main 8-K
   document is only a cover page. If no `EX-99.1` `.htm` exists, fall back
   to the first `EX-99.x` `.htm` in the table. Use the link in that row for
   the download, and if the link starts with `/ix?doc=`, remove that prefix
   so the URL points at the document itself.
5. Downloads that exhibit and converts the HTML to plain text with
   BeautifulSoup: remove `script` and `style` tags, extract the text with
   spaces between elements, and collapse all runs of whitespace (including
   non-breaking spaces) to a single space.
6. Extracts the following from the plain text using regular expressions:
   - **Reporting period**: the fiscal quarter the release covers, as a
     short string such as `"third quarter fiscal 2026"`. Releases phrase
     this differently (for example "fiscal 2026 third quarter" versus
     "third quarter fiscal 2026" versus "second quarter 2026"), so the
     pattern must accept quarter-then-year and year-then-quarter orderings
     and normalize the result to `"<quarter> quarter fiscal <year>"` or
     `"<quarter> quarter <year>"` as the release states it.
   - **Quarterly revenue**: the total revenue (for JPMorgan, total net
     revenue as reported, not the "managed basis" figure) for the quarter,
     not year-to-date and not a segment. Convert it to a single universal
     unit, **millions of US dollars**, stored as a plain number with no
     dollar sign, commas, or unit word, so that every row in the CSV is
     directly comparable. For example "$109.4 billion" becomes `109400.0`,
     "$28,000 million" becomes `28000.0`, and a table figure of `28,000,000`
     under a "(in thousands)" header becomes `28000.0`. Handle "billion" and
     "million" wording in the text, and for figures taken from a financial
     table, read the table's unit header ("in millions", "in thousands", or
     "in billions") and convert accordingly.
   - **Diluted EPS**: GAAP diluted earnings per share for the quarter, as
     a plain number in dollars with no dollar sign (for example `4.81`).
     If a release gives both GAAP and non-GAAP diluted EPS, use the GAAP
     figure.
   - **Net income**: GAAP net income for the quarter (for Walmart and
     JPMorgan use net income attributable to the company / common
     shareholders as stated), converted to millions of US dollars as a
     plain number using the same rules as revenue (for example "$35.8
     billion" becomes `35800.0`). If a release gives both GAAP
     and non-GAAP net income, use GAAP. If net income is not stated in the
     narrative text, look for the "Net income" row in the income-statement
     table in the same text.
   - If revenue, EPS, or net income cannot be found in the `EX-99.1` text,
     download up to two other `EX-99.x` `.htm` exhibits from the same
     filing and search those for the missing fields before giving up and
     storing `"NOT_FOUND"`. Only use these other exhibits to fill fields
     that are still missing; never overwrite a value already found.
7. Prints the extracted row for each filing as soon as it is processed, in
   exactly this format:
   `[Ticker] | [Period] | Revenue: $X | EPS: $X | Net Income: $X`
   with revenue and net income shown in millions of dollars, with a
   thousands separator and an `M` suffix for readability (for example
   `AAPL | third quarter fiscal 2026 | Revenue: $109,400M | EPS: $2.01 | Net Income: $27,000M`).
   Fields that could not be extracted print as `NOT_FOUND` (so a missing
   revenue prints as `Revenue: NOT_FOUND`, without a dollar sign).
8. Saves all rows to `hw03/earnings_history.csv` with exactly these
   columns, in this order: `company`, `ticker`, `cik`, `filing_date`,
   `period`, `revenue_reported`, `eps_diluted`, `net_income`. Use the
   company name exactly as written in the table above for `company`. Write
   `cik` as the 10-digit zero-padded string, `filing_date` as
   `YYYY-MM-DD`, `revenue_reported` and `net_income` as plain numbers in
   millions of US dollars (for example `109400.0`, with no `$`, commas, or
   suffix), and `eps_diluted` as a plain number in dollars. Overwrite the
   file on each run. The columns keep the names `revenue_reported` and
   `net_income`; both are always in millions of USD.
9. When a field cannot be extracted (the regular expression returns no
   match), stores the string `"NOT_FOUND"` in that cell. Never store
   `None`, an empty string, or leave the cell blank. Blank cells and
   missing data are two different things.
10. Prints a final confirmation line stating how many rows were saved and
    the path of the CSV, plus a count of how many rows contain at least one
    `NOT_FOUND`.
11. Includes a comment block at the very top of the script identifying its
    purpose, the data source, the author (Jonah Karst), and the date it was
    generated.

## Error handling (the script must never crash on a single bad filing)

- Wrap the processing of each individual filing in a try/except. If the
  filing index cannot be loaded, if no press-release exhibit can be found,
  if a download fails or times out, or if anything unexpected is raised,
  print a clear warning that names the ticker, filing date, and reason,
  then continue to the next filing. Where the filing was selected but no
  exhibit text could be obtained, still write a row for that filing (with
  `company`, `ticker`, `cik`, and `filing_date` filled in) with
  `"NOT_FOUND"` in `period`, `revenue_reported`, `eps_diluted`, and
  `net_income`, and print it in the standard row format, so the CSV and
  the console both show that the filing existed.
- Wrap each company the same way so that a failure on one company never
  stops the other four.
- Retry a failed HTTP request once after a 2-second pause before giving up.

## Important constraints

- This must be **one single Python script** that runs from the command
  line as `python hw03/hw03_earnings.py` and finishes in one execution.
- Build the output path from the script's own location (for example with
  `pathlib.Path(__file__).parent`) so `earnings_history.csv` is written
  into the `hw03/` folder no matter which directory the script is run from.
- Configure the script so that printing never fails on Windows: press
  releases contain characters (dashes, curly quotes, non-breaking spaces)
  that the default Windows console encoding cannot print. Reconfigure
  standard output to UTF-8 at startup and open the CSV with
  `encoding="utf-8"` and `newline=""`.
- Keep each regular expression in a clearly named variable near the top of
  the script (for example `REVENUE_PATTERNS`), with a one-line comment on
  what each matches, so that a failing pattern can be found and replaced
  later without reading the whole script.
- Use clear, readable print statements with labels so the terminal output
  is easy to follow without reading the code alongside it.

---

# Specification B: Executive Events Pipeline (Item 5.02)

## Purpose

I need one single Python script, `hw03/hw03_executives.py`, that finds every
executive and director change disclosed by five public companies in the past
12 months via SEC Form 8-K Item 5.02, reads each filing, and saves one row per
individual departure or appointment to a CSV. It must run start to finish in
a single execution, must never crash because one filing is hard to parse, and
must treat "no events found" as valid data rather than an error.

## Data source and companies

The source is the SEC EDGAR submissions API at
`https://data.sec.gov/submissions/CIK{cik}.json`, where `{cik}` is the
10-digit zero-padded CIK exactly as written below. Use these values exactly:

| Company | Ticker | CIK |
|---|---|---|
| Apple Inc. | AAPL | 0000320193 |
| Microsoft Corporation | MSFT | 0000789019 |
| NVIDIA Corporation | NVDA | 0001045810 |
| JPMorgan Chase & Co. | JPM | 0000019617 |
| Walmart Inc. | WMT | 0000104169 |

Required packages are `requests` and `beautifulsoup4` only. Do not use
pandas, lxml, or any package beyond the standard library plus those two
(the standard `csv` and `datetime` modules are fine).

## Requirements

Please write one Python script that does all of the following, in this
order, in a single execution:

1. Defines the header `{"User-Agent": "MIS3060 Villanova jkarst@villanova.edu"}`
   once and sends it on **every** `requests.get()` call in the script,
   including the submissions API call and every filing download. The
   simplest way to guarantee this is one small helper function that all HTTP
   requests go through. Set a timeout of 30 seconds on every request, and
   pause 0.2 seconds between requests to stay well under the SEC's
   10-requests-per-second limit.
2. Calculates the cutoff date as today's date minus 365 days, computed at
   run time (never hard-coded).
3. For each of the five companies, calls the submissions API and reads the
   `filings.recent` arrays (`form`, `items`, `filingDate`,
   `accessionNumber`, `primaryDocument`). Keeps only entries where `form` is
   exactly `"8-K"`, the `items` field, split on commas, contains exactly
   `"5.02"` (Departure of Directors or Certain Officers; Election of
   Directors; Appointment of Certain Officers), and `filingDate` is on or
   after the cutoff date. Do not match on substring, and do not include
   `8-K/A` amendments. Sort newest first. The `recent` arrays always cover
   the past 12 months, so do not follow the older-filings links in the
   response.
4. For each matching filing, builds the URL of the filing's main document as
   `https://www.sec.gov/Archives/edgar/data/{cik without leading zeros}/{accession number without dashes}/{primaryDocument}`,
   downloads it, and converts the HTML to plain text with BeautifulSoup:
   remove `script` and `style` tags, extract the text with spaces between
   elements, and collapse all runs of whitespace (including non-breaking
   spaces) to a single space. Most Item 5.02 filings carry their content in
   the main 8-K document. If, however, the Item 5.02 section (see the next
   step) is shorter than 400 characters or says the details are in an
   attached press release or exhibit (for example "Exhibit 99.1"), also
   download the filing's `EX-99.1` `.htm` exhibit and extract from that
   text as well. Find it by downloading the filing index page at
   `https://www.sec.gov/Archives/edgar/data/{cik without leading zeros}/{accession number without dashes}/{accession number with dashes}-index.html`
   and reading the table with class `tableFile`: the row whose **Type**
   column is `EX-99.1` and whose file ends in `.htm`. Use that row's link
   for the download, and if the link starts with `/ix?doc=`, remove that
   prefix.
5. From the text of the Item 5.02 section only, extracts each distinct
   executive or director change. To isolate the section: find the
   occurrences of the words "Item 5.02" in the text and, because the phrase
   can also appear in cross-references, use the occurrence that is followed
   by the longest stretch of text before the next "Item" heading (for
   example "Item 7.01" or "Item 9.01") or the "SIGNATURE" block. This keeps
   other items in the same filing from creating false matches. Then, for
   each change:
   - **event_type**: `"departure"` if a person is leaving, resigning,
     retiring, being terminated, or not standing for re-election;
     `"appointment"` if a person is being appointed, elected, or promoted
     into a role; `"both"` only when the **same person** leaves one role and
     takes another in the same filing (for example, a CFO who steps down
     from the CFO role and becomes an advisor or chair).
   - **person_name**: the person's full name (first and last, including any
     middle initial that appears).
   - **title**: the role being left or taken (for example "Chief Financial
     Officer" or "Director"), as written in the filing. For a `both` event,
     write the role being left, then ` -> `, then the role being taken (for
     example "Chief Financial Officer -> Senior Advisor").
   - **effective_date**: the date the change takes effect, normalized to
     `YYYY-MM-DD`. If the filing says the change is effective immediately
     or as of the date of the report, use the filing date. If the filing
     gives no effective date at all, store `"NOT_FOUND"`; never invent a
     date.
6. If one filing reports more than one event (for example one person
   departing and a different person appointed), creates a **separate row for
   each event**. A single filing can therefore produce several rows. A
   `both` event (one person, one row) counts as a single event, so a filing
   that only reports one person changing roles produces one row, not two.
7. Prints each extracted event as soon as it is processed, in exactly this
   format: `[Ticker] | [Date] | [Event Type] | [Name] | [Title]` where
   `[Date]` is the filing date.
8. If a company has **no** Item 5.02 filings in the past 12 months, prints
   exactly `[Ticker]: No executive events in past 12 months` (for example
   `JPM: No executive events in past 12 months`) and moves on. This is
   valid data, not an error, and the company must still be reported in the
   console output rather than silently skipped.
9. Saves all events to `hw03/executive_events.csv` with exactly these
   columns, in this order: `company`, `ticker`, `cik`, `filing_date`,
   `event_type`, `person_name`, `title`, `effective_date`. Write `cik` as
   the 10-digit zero-padded string and dates as `YYYY-MM-DD`. Overwrite the
   file on each run. If there are zero events across all five companies,
   still write the file with just the header row.
10. When a field cannot be extracted, stores the string `"NOT_FOUND"` in that
    cell. Never store `None`, an empty string, or leave the cell blank. This
    applies to `person_name`, `title`, and `effective_date`. The
    `event_type` column only ever holds `departure`, `appointment`, or
    `both`, so that the timeline built from this file counts real events
    only. Handle Item 5.02 filings that contain no departure or appointment
    (for example, a filing that only describes a compensation plan or
    award) as follows:
    - If the Item 5.02 text contains departure or appointment language but
      the name or title cannot be pulled out cleanly, still write a row with
      the `event_type` the language indicates and `"NOT_FOUND"` in the
      fields that failed, and print a warning. A parsing failure must stay
      visible in the data.
    - If the Item 5.02 text contains no departure or appointment language at
      all, write **no row** for that filing, and print
      `[Ticker] | [Date] | Item 5.02 filing with no departure or appointment (compensation or other) - skipped`.
      Such a filing does not count as a company having zero events; it is
      still counted as an Item 5.02 filing reviewed.
11. Prints a final confirmation line stating how many Item 5.02 filings were
    reviewed, how many events were saved, how many filings were skipped for
    having no departure or appointment, how many companies had zero Item
    5.02 filings, and the path of the CSV.
12. Includes a comment block at the very top of the script identifying its
    purpose, the data source, the author (Jonah Karst), and the date it was
    generated.

## Error handling (the script must never crash on a single bad filing)

- Wrap the processing of each individual filing in a try/except. If a
  download fails or times out, or if anything unexpected is raised, print a
  clear warning naming the ticker, filing date, and reason, then continue to
  the next filing.
- Wrap each company the same way so that a failure on one company never
  stops the other four.
- Retry a failed HTTP request once after a 2-second pause before giving up.

## Important constraints

- This must be **one single Python script** that runs from the command line
  as `python hw03/hw03_executives.py` and finishes in one execution.
- Build the output path from the script's own location (for example with
  `pathlib.Path(__file__).parent`) so `executive_events.csv` is written into
  the `hw03/` folder no matter which directory the script is run from.
- Configure the script so that printing never fails on Windows: filings
  contain characters (dashes, curly quotes, non-breaking spaces) that the
  default Windows console encoding cannot print. Reconfigure standard
  output to UTF-8 at startup and open the CSV with `encoding="utf-8"` and
  `newline=""`.
- Keep the regular expressions and the keyword lists that classify departure
  versus appointment in clearly named variables near the top of the script
  (for example `DEPARTURE_KEYWORDS`, `APPOINTMENT_KEYWORDS`), with a
  one-line comment on each, so they can be tuned later without reading the
  whole script.
- Use clear, readable print statements with labels so the terminal output
  is easy to follow without reading the code alongside it.
