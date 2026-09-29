# AI Usage Log
**Assignment:** HW3: Building a Corporate Intelligence Database from SEC 8-K Filings
**Student:** Jonah Karst
**Date:** 9/29/26

---

## Tool and workflow

All work was done in VS Code with Claude Code (Claude Sonnet 5.5), not Claude Cowork. Claude Code generated each script from the plain-English specifications below; I ran every script myself in the terminal to produce the deliverable CSVs and pasted the output back for review. Before each of my runs, Claude Code also tested the code against saved copies of the real filings, writing to scratch files outside the repository, and it made one smoke run of the Yahoo Finance script; the deliverable CSVs in `hw03/` all came from my own runs. The three scripts were generated in one continuous Claude Code session rather than three separate conversations. `hw03/specifications.md` was finished before any code was generated (its last edit predates every script). Two decisions changed during Part 1, before any code: revenue and net income use one universal unit (millions of USD) instead of the units each release reports, and the CSVs are written to `hw03/` itself, as the assignment specifies.

## The three prompts

### Prompt 1: Specification A (earnings pipeline, Item 2.02)

Produced `hw03/hw03_earnings.py`. The full text sent:

````markdown
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
````

### Prompt 2: Specification B (executive events pipeline, Item 5.02)

Produced `hw03/hw03_executives.py`. The full text sent:

````markdown
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
````

### Prompt 3: timeline prompt (assignment text, unchanged)

Produced `hw03/hw03_timeline.py`. The prompt sent, verbatim from the assignment:

> "Write a Python script that reads `hw03/earnings_history.csv` and `hw03/executive_events.csv`. Do the following:
>
> 1. For each executive event in the events table, calculate the number of days between the executive event's `filing_date` and the nearest earnings filing date for the same company in the earnings table. Call this `days_to_nearest_earnings`.
> 2. Add a column `event_timing` that categorizes each executive event as: `'before earnings'` if the event came before the nearest earnings filing, `'after earnings'` if it came after, or `'same week'` if within 7 days of an earnings filing.
> 3. Save the combined table to `hw03/corporate_events_timeline.csv` with all columns from both source tables plus `days_to_nearest_earnings` and `event_timing`.
> 4. Print a summary: for each company, list any executive events and whether they occurred before or after the nearest earnings announcement.
> 5. Print a final count: how many events occurred before vs. after an earnings announcement across all five companies."

The prompt left three things open that the generated script had to decide: (a) both tables share the columns `company`, `ticker`, `cik`, and `filing_date`, so `company`, `ticker`, and `cik` appear once and the earnings table's date is named `earnings_filing_date`; (b) `days_to_nearest_earnings` is stored as an absolute number of days, with `event_timing` carrying the direction; (c) same-week events get their own bucket in the final count so the before and after totals are not blurred. The timeline script needed no logic fixes; one wording change to the printed summary (making same-week lines say "6 days before" instead of an ambiguous phrase) was made before I ran it.

No prompt was sent to a new session to ask for a regex fix, which the assignment suggests when a company returns all `NOT_FOUND`. No company did. Every fix below was made in the same session, from reading the script's output or from a validation check.

## Which companies' extractions required iteration

| Pipeline | Company | What needed fixing | How it was found |
|---|---|---|---|
| Earnings | Apple | Net income came out 1,000x too small ($29.8M instead of $29,789M). Apple's table header reads "(In millions, except number of shares, which are reflected in **thousands**...)" and the unit finder took the last unit in the header instead of the first. | My first run's output (I pasted it back and Claude Code spotted the pattern in the four Apple rows). |
| Earnings | Microsoft | (1) The non-GAAP filter treated "non-GAAP basis" at the end of the previous bullet as a label on the next EPS line and dropped the GAAP EPS. (2) Period is written "FY26 Q4". (3) Revenue and net income were rounded prose figures (90,000 instead of 90,007). | (1) and (2): testing the extractors on text modeled on the releases before my first run. (3): validation 5A against Microsoft's official figure. |
| Earnings | JPMorgan | Period is written "Second-quarter 2026" (hyphen) and EPS is written "$5.07 per share" without the word "diluted". | Testing before my first run. |
| Earnings | Walmart | Period is written "Fiscal Year 2027 Q2". | Testing before my first run. |
| Earnings | NVIDIA, Apple, Walmart | Revenue was rounded prose (for example 96,200 instead of 96,221). Fixed by the same change as Microsoft's. | Validation 5A; the fix was then tested on all 20 filings. |
| Executives | All five | Section handling: the Item 5.02 heading itself contains "Departure", "Election", "Appointment", so it had to be removed before classifying. Apostrophes came out as a broken character because the response text was decoded wrongly, so the script parses the raw bytes. | Reading the real Item 5.02 text of all 19 filings before writing the script. |
| Executives | Walmart | False people ("Non-Compete Agreement", "Non-Competition Agreements"), titles cut off at "Walmart U.S", and "succeeds X in this role" departures with no title or the wrong date (Furner, McLay). | Running the script logic on the 19 real filings and comparing each row with the filing text. |
| Executives | NVIDIA | "Ms. Nora Johnson" duplicated "Suzanne Nora Johnson"; Puri's title came out as the single word "role" and his effective date was `NOT_FOUND` although the filing ties it to his successor's start date. | Same comparison; the Puri date fix came after my first run. |
| Executives | Apple | Levinson's title ended with "on the Transition Date"; Kondo and Adams (successor links) had no effective date. The Transition Date is defined elsewhere in the filing as September 1, 2026. | Same comparison. |
| Executives | JPMorgan | The title for Petno and Rohrbaugh was plural ("Co-Presidents"). | Reviewing my first run's output. |
| Executives | All | Titles were sometimes lowercase ("general counsel"), unlike the rest. | Reviewing my first run's output. |
| Executives | Microsoft | None beyond the shared fixes. | |

The three `NOT_FOUND` effective dates left in the executive data (Hoffman and Rodriguez at Microsoft, Lake at JPMorgan) were investigated and are correct, because those filings state no date.

## One thing the generated script did that I would not have thought to specify

The executives script removes the Item 5.02 heading before deciding whether a filing contains a departure or an appointment. Every Item 5.02 filing begins with the standard heading "Departure of Directors or Certain Officers; Election of Directors; Appointment of Certain Officers; Compensatory Arrangements of Certain Officers", so a keyword search over the section finds both "departure" and "appointment" in every filing, including ones about only a stock plan or a bonus plan. Claude Code found this by reading the real filings first, and it removed the heading before classifying. It was correct as generated and needed no adjustment: it is why the three compensation-only filings (Microsoft's stock plan, NVIDIA's bonus plan, JPMorgan's CEO pay) were correctly skipped. My specification had not mentioned it. Two related unspecified choices were also right: parsing the raw bytes of each filing instead of the decoded text (to avoid corrupted apostrophes), and resolving dates written as a defined term, such as "effective on the Transition Date".

## Where the finished scripts differ from the specifications

- **Press-release fallback (Spec B):** the spec says to also read the EX-99.1 exhibit when the Item 5.02 section is under 400 characters or mentions an exhibit. The script does this only when the section produced no events, so it does not fetch exhibits it does not need (JPMorgan's complete 253-character resignation notice would otherwise trigger it). I left the spec unchanged so it stays the version written before coding.
- **Table precision (Spec A):** the spec did not say whether to prefer rounded prose figures or exact table figures. The pipeline first used prose, which validation 5A showed was too coarse. It now takes the prose figure and then replaces it with an exact table figure only if the table figure agrees within the prose's own rounding. JPMorgan's figures stay rounded to $0.1 billion because its main press release has no income statement table.
- **NOT_FOUND paths:** the earnings run produced no `NOT_FOUND` values, so the branches that write `NOT_FOUND` and handle a missing press release exist in the code but were not exercised on real data.

## What I checked myself versus what Claude Code told me

- I verified Microsoft's Q4 FY26 revenue and EPS against Microsoft's investor relations page (5A) and Carmine Di Sibio's appointment against Microsoft's news release (5B).
- The Yahoo Finance comparison (5C) matched exactly, and it came from a small script Claude Code wrote (`hw03/hw03_yfinance_check.py`) that I ran and pasted back.
- Early on, Claude Code suggested leaving Microsoft's $7 million revenue gap as an acceptable rounding difference. I pointed out that the assignment says to fix the pipeline when a value does not match, which was correct, and the fix improved the whole dataset.
