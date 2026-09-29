"""
hw03_executives.py

Purpose:     Find every executive and director change disclosed in the past
             12 months by five public companies through SEC Form 8-K
             Item 5.02, read each filing, and save one row per individual
             departure / appointment to a CSV.
Data source: SEC EDGAR submissions API
             (https://data.sec.gov/submissions/CIK{cik}.json) and the main
             8-K document of each Item 5.02 filing (plus its EX-99.1 press
             release when the 5.02 text itself has no usable details).
Output:      hw03/executive_events.csv
Author:      Jonah Karst
Generated:   2026-09-29

Run from the command line:
    python hw03/hw03_executives.py

Any field that cannot be extracted is stored as the string "NOT_FOUND".
event_type is always one of: departure, appointment, both.
"""

import csv
import re
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# Filings contain characters (dashes, curly quotes) that the default Windows
# console encoding cannot print, so force UTF-8 output.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
HEADERS = {"User-Agent": "MIS3060 Villanova jkarst@villanova.edu"}
REQUEST_TIMEOUT = 30          # seconds, applied to every request
REQUEST_PAUSE = 0.2           # seconds between requests (SEC limit: 10/sec)
RETRY_PAUSE = 2               # seconds before the single retry
LOOKBACK_DAYS = 365
MIN_SECTION_CHARS = 400       # shorter 5.02 sections trigger the exhibit fallback
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

OUTPUT_PATH = Path(__file__).resolve().parent / "executive_events.csv"
CSV_COLUMNS = [
    "company", "ticker", "cik", "filing_date",
    "event_type", "person_name", "title", "effective_date",
]

# ---------------------------------------------------------------------------
# Regular expressions and keyword lists (tune these if extraction fails)
# ---------------------------------------------------------------------------
MONTHS = ("January|February|March|April|May|June|July|August|"
          "September|October|November|December")
# "September 1, 2026" (tolerates "January 2 , 2026" spacing seen in some filings)
DATE_RE = re.compile(rf"(?P<m>{MONTHS})\s+(?P<d>\d{{1,2}})\s*,\s*(?P<y>\d{{4}})")

# The Item 5.02 heading. Its words ("Departure", "Election", "Appointment")
# must be removed before classifying, or every filing would look like an event.
HEADING_RE = re.compile(
    r"Item\s+5\.02(?:\s*\([a-z]\))*\s*\.?\s*"
    r"Departure\s+of\s+Directors\s+or\s+Certain\s+Officers\s*;\s*"
    r"Election\s+of\s+Directors\s*;\s*"
    r"Appointment\s+of\s+Certain\s+Officers\s*;\s*"
    r"Compensatory\s+Arrangements\s+of\s+Certain\s+Officers\s*\.?",
    re.IGNORECASE,
)
ITEM_502_RE = re.compile(r"Item\s+5\.02", re.IGNORECASE)
# End of an Item 5.02 section: the next Item heading (but not a 5.02 cross
# reference) or the SIGNATURE block.
SECTION_END_RE = re.compile(r"Item\s+(?!5\.02)\d\.\d{2}|SIGNATURES?")

# --- Departure / appointment language -------------------------------------
# Words in the text AFTER a person's name that show that person is leaving.
DEPARTURE_KEYWORDS = re.compile(
    r"\b(?:resign(?:ed|s)?|resignation|retire(?:d|s|ment)?|step(?:s|ped|ping)?\s+down|"
    r"not\s+(?:to\s+)?stand\s+for\s+re-?election|will\s+leave|depart(?:s|ed|ing|ure)?|"
    r"terminat(?:ed|ion)|removed|transition(?:s|ed)?\s+from)\b",
    re.IGNORECASE,
)
# Words directly BEFORE a person's name that show that person is leaving.
DEPARTURE_BEFORE_NAME = re.compile(
    r"(?:succeed(?:s|ed)?|replac(?:e|es|ed|ing)|duties\s+from|resignation\s+of|retirement\s+of|"
    r"departure\s+of)\s+(?:(?:Mr|Ms|Mrs|Dr)\.\s+)?$",
    re.IGNORECASE,
)
# Words in the text AFTER a person's name that show that person is starting a role.
APPOINTMENT_KEYWORDS = re.compile(
    r"\b(?:(?:has|have|had)\s+been\s+(?:appointed|elected|named|promoted|designated)|"
    r"(?:was|were)\s+(?:also\s+)?(?:appointed|elected|named|promoted|designated)|"
    r"will\s+(?:also\s+)?(?:become|be\s+(?:appointed|elected|named|promoted)|assume|join\s+(?:the\s+)?Board)|"
    r"will\s+serve\s+as|joins?\s+the\s+Board)\b",
    re.IGNORECASE,
)
# Words directly BEFORE a person's name that show that person is starting a role.
APPOINTMENT_BEFORE_NAME = re.compile(
    r"(?:appointed|appoint|elected|elect|named|promoted|promotion\s+of|designated|hired|nominated)\s+"
    r"(?:(?:Mr|Ms|Mrs|Dr)\.\s+)?$",
    re.IGNORECASE,
)
# Loose "is there any departure / appointment language at all" checks, used only
# to decide whether an Item 5.02 filing with no parsed events is a
# compensation-only filing (skipped) or a parsing failure (kept as a row).
ANY_DEPARTURE_LANGUAGE = re.compile(
    r"\b(?:resign\w*|retire\w*|step(?:s|ped|ping)?\s+down|not\s+(?:to\s+)?stand\s+for\s+re-?election|"
    r"terminat\w+|departure\s+of|transition\s+from|no\s+longer\s+serve)\b", re.IGNORECASE)
ANY_APPOINTMENT_LANGUAGE = re.compile(
    r"\b(?:appointed|appointment\s+of|elected\s+(?:as|to)|named\s+(?:as|to|the)|promoted|"
    r"will\s+become|has\s+been\s+elected|have\s+been\s+elected)\b", re.IGNORECASE)

# One person changing roles, e.g. "will transition from his role as Chief
# Executive Officer to Executive Chair of Apple's Board".
BOTH_TRANSITION_FROM_TO = re.compile(
    r"transition(?:s|ed)?\s+from\s+(?:his|her|their)\s+role\s+as\s+(?P<old>.+?)\s+to\s+(?P<new>[^.;]+)",
    re.IGNORECASE,
)
# e.g. "will continue to serve as the Company's SVP and Controller until ..., at
# which time he will transition to the role of SVP, Treasurer and Tax".
BOTH_CONTINUE_THEN_TRANSITION = re.compile(
    r"continue\s+to\s+serve\s+as\s+(?P<old>.+?)\s+until\s+[^.;]{0,100}?transition\s+to\s+"
    r"(?:the\s+role\s+of\s+)?(?P<new>[^.;]+)",
    re.IGNORECASE,
)

# --- Title extraction ------------------------------------------------------
# "appointed X, age 55, as <TITLE>"
TITLE_AFTER_AS = re.compile(r"\bas\s+(?!of\b)(?P<t>[^;]+)", re.IGNORECASE)
# "will become <TITLE>", "was appointed <TITLE>", "have been elected <TITLE>"
TITLE_AFTER_APPT_VERB = re.compile(
    r"(?:will\s+(?:also\s+)?become|(?:was|were|has\s+been|have\s+been)\s+(?:also\s+)?"
    r"(?:appointed|elected|named|promoted\s+to)|will\s+serve\s+as|will\s+be\s+"
    r"(?:appointed|elected|named))\s+(?P<t>[^;]+)",
    re.IGNORECASE,
)
# "retire from his role as <TITLE>", "from his position as <TITLE>"
TITLE_FROM_ROLE = re.compile(
    r"(?:from|as)\s+(?:his|her|their)\s+(?:role|position)(?:\s+as)?\s+(?P<t>[^;]+)", re.IGNORECASE)
# "resigned as / from <TITLE>", "retire from <TITLE>"
TITLE_AFTER_RESIGN = re.compile(
    r"(?:resign(?:ed|s)?|retire|step(?:s)?\s+down|stepping\s+down)\s+(?:from\s+|as\s+)"
    r"(?:the\s+|a\s+|his\s+|her\s+)?(?P<t>[^;]+)", re.IGNORECASE)
# ", who has served as <TITLE> since 2017"
TITLE_HAS_SERVED = re.compile(r"who\s+has\s+served\s+as\s+(?P<t>[^;]+)", re.IGNORECASE)
# ", <descriptor>, notified the Company ..." -- the title given right after the name
TITLE_DESCRIPTOR = re.compile(
    r"^,\s*(?:\d{1,2},\s*)?(?P<t>.+?),\s*(?:has\b|have\b|notified|informed|will\b|intend|resigned|"
    r"announced|advised|who\b|decided|submitted|tendered)", re.IGNORECASE)
# Where a title phrase ends.
TITLE_END = re.compile(
    r",\s+(?:effective|in\s+each\s+case|and\s+(?:will|is|was)|who|age|as\s+of|following|to\s+be|which|or\s+the)\b"
    r"|\s+(?:effective|until|since|beginning|following|because|due\s+to)\b"
    r"|\s+of\s+(?:the\s+)?(?:Company|Firm|Corporation)\b"
    r"|\s+of\s+(?:Apple|Microsoft|NVIDIA|Walmart(?!\s+U\.S)|JPMorgan\w*)\b"
    r"|\s+on\s+(?:" + MONTHS + r")\s+\d"
    r"|\s+on\s+the\s+[A-Z][\w ]{0,20}?\bDate\b"
    r"|\s+\(|;|\.(?:\s|$)|\s+and\s+as\s+a\b|\s+and\s+a\s+member\b"
)
COMPANY_POSSESSIVE = re.compile(
    r"^(?:the\s+)?(?:Company|Firm|Apple|Microsoft|NVIDIA|Walmart|JPMorgan\w*)[’'�]s\s+", re.IGNORECASE)
BOARD_MEMBER = re.compile(
    r"^(?:an?\s+|the\s+)?(?:independent\s+|non-employee\s+)?(?:member\s+of\s+(?:the\s+|its\s+|our\s+)?|"
    r"(?:the\s+)?)(?:[A-Za-z’'�]+\s+)?Board(?:\s+of\s+Directors)?\b", re.IGNORECASE)

# --- Names -------------------------------------------------------------------
# One capitalized name word (McMillon, Di, Nora, K.) and a run of 2-4 of them.
NAME_TOKEN = r"(?:[A-Z][a-z]+(?:[A-Z][a-z]+)*(?:[-'’�][A-Z][a-z]+)*|[A-Z]\.)"
NAME_RUN = re.compile(rf"(?:{NAME_TOKEN})(?:\s+{NAME_TOKEN}){{1,3}}")
# Capitalized words that are never part of a person's name in these filings.
NAME_STOPWORDS = {
    "on", "in", "the", "as", "at", "by", "following", "upon", "since", "prior", "effective", "additionally",
    "mr", "ms", "mrs", "dr", "messrs", "item", "board", "directors", "director", "company", "corporation",
    "committee", "compensation", "audit", "officer", "officers", "chief", "executive", "vice", "president",
    "senior", "general", "counsel", "secretary", "firm", "plan", "stock", "inc", "corp", "annual",
    "shareholders", "shareholder", "meeting", "regulation", "exchange", "act", "commission", "securities",
    "form", "apple", "microsoft", "nvidia", "walmart", "jpmorgan", "jpmorganchase", "chase", "bank", "group",
    "awards", "award", "retention", "continuity", "operating", "management", "development", "technology",
    "fiscal", "year", "proxy", "statement", "exhibit", "principal", "accounting", "financial", "chair",
    "chairman", "lead", "independent", "date", "transition", "amazon", "intel", "oracle", "sam", "club",
    "worldwide", "field", "operations", "hardware", "engineering", "consumer", "community", "banking",
    "investment", "commercial", "asset", "wealth", "controller", "treasurer", "tax", "co", "ceo", "cfo",
    "coo", "cao", "vp", "evp", "svp", "sole", "new", "there", "he", "she", "his", "her", "this", "that",
    "no", "any", "each", "all", "our", "its", "under", "pursuant", "in-connection", "united", "states",
    "america", "nasdaq", "stock", "market", "llc", "ltd", "technologies", "solutions", "sales", "partner",
    "industry", "business", "global", "eecommerce", "ecommerce", "supply", "chain", "innovation",
    "automation", "product", "audit", "internal", "risk", "legal", "nominating", "governance",
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
    "incentive", "agreement", "agreements", "non-compete", "non-competition", "non-solicitation",
    "confidentiality", "policy", "equity", "restricted", "severance", "employment", "separation",
    "release", "claims", "amendment", "annex", "schedule", "cmdc", "supply", "performance", "units",
} | {m.lower() for m in MONTHS.split("|")}
HONORIFIC_BEFORE = re.compile(r"(?:Mr|Ms|Mrs|Dr)\.\s+$")

ABBREVIATIONS = re.compile(r"\b(Mr|Ms|Mrs|Dr|Inc|Corp|Co|Ltd|Jr|Sr|St|No|vs|Messrs|Mses)\.")
INITIALS = re.compile(r"\b([A-Z])\.(?=\s)")
US_ABBREV = re.compile(r"\bU\.S\.")


# ---------------------------------------------------------------------------
# HTTP and text helpers
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


def html_to_text(content):
    """Strip HTML (bytes or str) to plain text with single spaces."""
    soup = BeautifulSoup(content, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    text = soup.get_text(" ")
    return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()


def parse_date(match):
    """Turn a DATE_RE match into YYYY-MM-DD."""
    return datetime.strptime(f"{match.group('m')} {match.group('d')} {match.group('y')}", "%B %d %Y").strftime("%Y-%m-%d")


def split_sentences(text):
    """Split text into sentences without breaking on Mr., Inc., initials, U.S."""
    protected = ABBREVIATIONS.sub(lambda m: m.group(1) + "\x00", text)
    protected = US_ABBREV.sub("U\x00S\x00", protected)
    protected = INITIALS.sub(lambda m: m.group(1) + "\x00", protected)
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z“\"'(])", protected)
    return [part.replace("\x00", ".").strip() for part in parts if part.strip()]


# ---------------------------------------------------------------------------
# EDGAR navigation
# ---------------------------------------------------------------------------
def get_502_filings(cik, cutoff):
    """8-K filings with exact item 5.02 filed on/after cutoff, newest first."""
    data = http_get(SUBMISSIONS_URL.format(cik=cik)).json()
    recent = data["filings"]["recent"]
    filings = []
    for form, items, filing_date, accession, primary in zip(
        recent["form"], recent["items"], recent["filingDate"],
        recent["accessionNumber"], recent["primaryDocument"],
    ):
        item_list = [item.strip() for item in items.split(",")]
        if form == "8-K" and "5.02" in item_list and filing_date >= cutoff:
            filings.append({"filing_date": filing_date, "accession": accession, "primary": primary})
    filings.sort(key=lambda f: f["filing_date"], reverse=True)
    return filings


def filing_folder(cik, accession):
    return FILING_FOLDER.format(cik_int=int(cik), acc_nodash=accession.replace("-", ""))


def find_press_release_url(cik, accession):
    """URL of the EX-99.1 .htm exhibit from the filing index page, or None."""
    index_html = http_get(filing_folder(cik, accession) + accession + "-index.html").text
    soup = BeautifulSoup(index_html, "html.parser")
    for table in soup.find_all("table", class_="tableFile"):
        for row in table.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) < 4 or cells[3].get_text(strip=True).upper() != "EX-99.1":
                continue
            link = cells[2].find("a")
            if link is None or not link.get("href", "").lower().endswith(".htm"):
                continue
            href = link["href"].replace("/ix?doc=", "")
            return href if href.startswith("http") else ARCHIVE_ROOT + href
    return None


# ---------------------------------------------------------------------------
# Item 5.02 section isolation
# ---------------------------------------------------------------------------
def isolate_502_section(text):
    """Return the Item 5.02 text (heading removed), or '' if none is found.

    "Item 5.02" can also appear in cross-references, so use the occurrence that
    is followed by the longest stretch of text before the next Item or the
    SIGNATURE block.
    """
    best = ""
    for start in (m.start() for m in ITEM_502_RE.finditer(text)):
        end_match = SECTION_END_RE.search(text, start + 8)
        end = end_match.start() if end_match else len(text)
        section = text[start:end]
        if len(section) > len(best):
            best = section
    best = HEADING_RE.sub(" ", best, count=1)
    # If the heading was worded differently, at least drop the leading "Item 5.02".
    best = ITEM_502_RE.sub(" ", best, count=1) if best.lstrip().lower().startswith("item 5.02") else best
    return re.sub(r"\s+", " ", best).strip()


# ---------------------------------------------------------------------------
# Event extraction
# ---------------------------------------------------------------------------
def clean_title(raw):
    """Cut a captured title phrase at its natural end and tidy it."""
    if not raw:
        return None
    title = raw.strip()
    end = TITLE_END.search(title)
    if end:
        title = title[:end.start()]
    title = title.strip(" ,.;:")
    title = re.sub(r"\bU\.S$", "U.S.", title)
    if re.match(r"effective\b", title, re.IGNORECASE) or title.lower() in {"role", "position"}:
        return None
    title = re.sub(r"^(?:current|former|our)\s+", "", title, flags=re.IGNORECASE)
    title = COMPANY_POSSESSIVE.sub("", title)
    title = re.sub(r"^(?:a|an|the)\s+", "", title, flags=re.IGNORECASE)
    if BOARD_MEMBER.match(title) and not re.match(r"(?:Lead|Independent|Executive)\b", title):
        return "Director"
    if not title or len(title) > 120 or re.match(r"(?:the\s+)?(?:Firm|Company|Corporation)\b", title, re.IGNORECASE):
        return None
    title = re.sub(r"\b(Co-)?Presidents\b", r"\1President", title)   # one person holds one title
    if title == title.lower():                                       # "general counsel" -> "General Counsel"
        small_words = {"and", "of", "the", "to", "for", "in"}
        title = " ".join(w if i and w in small_words else w[:1].upper() + w[1:] for i, w in enumerate(title.split(" ")))
    return title


def find_names(sentence):
    """Candidate person names in a sentence: [(name, start, end), ...]."""
    names = []
    for run in NAME_RUN.finditer(sentence):
        tokens = list(re.finditer(NAME_TOKEN, run.group(0)))
        words = [t.group(0) for t in tokens]
        # Trim stop words from both ends of the run ("On David Guggina").
        while words and words[0].lower().rstrip(".") in NAME_STOPWORDS:
            words.pop(0)
            tokens.pop(0)
        while words and words[-1].lower().rstrip(".") in NAME_STOPWORDS:
            words.pop()
            tokens.pop()
        if len(words) < 2 or any(w.lower().rstrip(".") in NAME_STOPWORDS for w in words):
            continue
        if not any(len(w.rstrip(".")) > 1 for w in words):
            continue
        start = run.start() + tokens[0].start()
        end = run.start() + tokens[-1].end()
        names.append((" ".join(words), start, end))
    return names


def effective_date_for(sentence, name_start, filing_date, defined_dates):
    """Effective date (YYYY-MM-DD) for the change described around a name."""
    head = sentence[:name_start]
    tail = sentence[name_start:]
    lead = re.match(r"\W*effective\s+(?:as\s+of\s+|on\s+)?" + DATE_RE.pattern, head, re.IGNORECASE)
    if lead:
        return parse_date(DATE_RE.search(head))

    effective = re.search(r"\beffective\b", tail, re.IGNORECASE)
    if effective:
        after = tail[effective.end():]
        if re.match(r"\s+immediately\b", after, re.IGNORECASE):
            return filing_date
        window = after[:160]
        date_match = DATE_RE.search(window)
        term = next((t for t in defined_dates if t in window.lower()), None)
        if term and (not date_match or window.lower().find(term) < date_match.start()):
            return defined_dates[term]
        if date_match:
            return parse_date(date_match)

    for term, value in defined_dates.items():
        if re.search(r"\b(?:on|as\s+of)\s+the\s+" + re.escape(term), tail, re.IGNORECASE):
            return value
    on_date = re.search(r"\bon\s+" + DATE_RE.pattern, tail)
    if on_date:
        return parse_date(on_date)
    return NOT_FOUND


def find_defined_dates(text):
    """Map defined terms to dates, e.g. 'transition date' -> '2026-09-01'."""
    defined = {}
    for match in re.finditer(
        DATE_RE.pattern + r"\s*\(\s*(?:the\s+)?[“\"�]+(?P<term>[^”\"�)]+)[”\"�]+\s*\)", text
    ):
        defined[match.group("term").strip().lower()] = parse_date(match)
    return defined


def classify_and_title(sentence, names, index):
    """Return (event_type, title) for names[index] in this sentence, or None."""
    name, start, end = names[index]
    next_start = names[index + 1][1] if index + 1 < len(names) else len(sentence)
    before = sentence[max(0, start - 80):start]
    after = sentence[end:next_start]
    full_after = sentence[end:]

    # A single person changing roles.
    both = BOTH_TRANSITION_FROM_TO.search(full_after) or BOTH_CONTINUE_THEN_TRANSITION.search(full_after)
    if both:
        old, new = clean_title(both.group("old")), clean_title(both.group("new"))
        title = f"{old} -> {new}" if old and new else (old or new or NOT_FOUND)
        return "both", title, False

    before_match = DEPARTURE_BEFORE_NAME.search(before)
    departure_before = bool(before_match)
    # "succeeds X" / "duties from X": X is leaving the role the new person takes.
    successor_link = bool(before_match and re.search(r"succeed|replac|duties", before_match.group(0), re.IGNORECASE))
    appointment_before = bool(APPOINTMENT_BEFORE_NAME.search(before))
    departure_after = bool(DEPARTURE_KEYWORDS.search(after))
    appointment_after = bool(APPOINTMENT_KEYWORDS.search(after))

    if departure_before:
        event = "departure"
    elif appointment_before:
        event = "appointment"
    elif departure_after and appointment_after:
        event = "both"
    elif departure_after:
        event = "departure"
    elif appointment_after:
        event = "appointment"
    else:
        return None

    # "current Chair of the Board, will become Lead Independent Director": leaving one role for another.
    descriptor = TITLE_DESCRIPTOR.search(after)
    if event == "appointment" and descriptor and re.match(r"\s*current\b", descriptor.group("t"), re.IGNORECASE) \
            and re.search(r"will\s+become", after, re.IGNORECASE):
        old = clean_title(descriptor.group("t"))
        new_match = TITLE_AFTER_APPT_VERB.search(after)
        new = clean_title(new_match.group("t")) if new_match else None
        if old and new:
            return "both", f"{old} -> {new}", False

    if event == "appointment":
        finders = [TITLE_AFTER_AS, TITLE_AFTER_APPT_VERB] if appointment_before else [TITLE_AFTER_APPT_VERB, TITLE_AFTER_AS]
        title = None
        for finder in finders:
            found = finder.search(after)
            title = clean_title(found.group("t")) if found else None
            if title:
                break
        if not title and re.search(r"\b(?:to|on)\s+(?:its|the|our)\s+(?:\w+\s+)?Board", after, re.IGNORECASE):
            title = "Director"
    else:  # departure or both without explicit roles
        title = None
        for finder in (TITLE_FROM_ROLE, TITLE_AFTER_RESIGN, TITLE_HAS_SERVED):
            found = finder.search(after)
            title = clean_title(found.group("t")) if found else None
            if title:
                break
        if not title:
            found = TITLE_DESCRIPTOR.search(after)
            title = clean_title(found.group("t")) if found else None
        if not title:
            found = re.search(r"in\s+(?:the|this)\s+role\s+of\s+(?P<t>[^.;]+)", after, re.IGNORECASE)
            title = clean_title(found.group("t")) if found else None
        if not title and re.search(r"\b(?:from|as\s+a\s+member\s+of)\s+the\s+Board", after, re.IGNORECASE):
            title = "Director"
    return event, title or NOT_FOUND, successor_link


def extract_events(text, filing_date):
    """Extract [(event_type, name, title, effective_date), ...] from 5.02 text."""
    defined_dates = find_defined_dates(text)
    events, surnames, event_sentence = [], set(), []
    last_appointment = None      # most recent appointment event, for "succeeds X" links
    sentences = split_sentences(text)
    for sentence_index, sentence in enumerate(sentences):
        names = find_names(sentence)
        results = [classify_and_title(sentence, names, i) for i in range(len(names))]
        # "Doug Petno, 61, and Troy Rohrbaugh, 56, ... have been elected": a name with
        # no verb of its own, joined by "and" to the next name, shares that name's event.
        for i in range(len(names) - 2, -1, -1):
            if results[i] is None and results[i + 1] is not None:
                between = sentence[names[i][2]:names[i + 1][1]]
                if re.fullmatch(r"[\s,\d]*(?:and\s*)?[\s,\d]*", between):
                    results[i] = results[i + 1]

        sentence_events = []      # (event list index, successor_link) for this sentence
        for (name, start, _), result in zip(names, results):
            if result is None:
                continue
            surname = name.split()[-1].lower()
            if surname in surnames:          # "Ms. Nora Johnson" after "Suzanne Nora Johnson"
                continue
            surnames.add(surname)
            event_type, title, successor_link = result
            effective = effective_date_for(sentence, start, filing_date, defined_dates)
            events.append([event_type, name, title, effective])
            event_sentence.append(sentence_index)
            sentence_events.append((len(events) - 1, successor_link))

        # A departure that only says "succeeded by X": borrow X's role and effective date.
        appointee = next((events[i] for i, _ in sentence_events if events[i][0] == "appointment"), last_appointment)
        for index, successor_link in sentence_events:
            if successor_link and appointee:
                if events[index][2] == NOT_FOUND:
                    events[index][2] = appointee[2]
                if appointee[3] != NOT_FOUND:
                    events[index][3] = appointee[3]
        appointments = [events[i] for i, _ in sentence_events if events[i][0] == "appointment"]
        if appointments:
            last_appointment = appointments[-1]

    # No date in the person's own sentence: look at the next two sentences that start
    # with the same honorific + surname ("Ms. McLay will remain ... effective as of ...").
    for event, sentence_index in zip(events, event_sentence):
        if event[3] != NOT_FOUND:
            continue
        surname = re.escape(event[1].split()[-1])
        for following in sentences[sentence_index + 1:sentence_index + 3]:
            if re.match(rf"(?:Mr|Ms|Mrs|Dr)\.\s+{surname}\b", following) and re.search(r"\beffective\b", following, re.IGNORECASE):
                found = effective_date_for(following, 0, filing_date, defined_dates)
                if found != NOT_FOUND:
                    event[3] = found
                    break

    # "retire ... effective upon the employment commencement date of his successor":
    # the filing ties the departure to the successor's start, so use that appointment's date.
    for index, (event, sentence_index) in enumerate(zip(events, event_sentence)):
        if event[0] == "departure" and event[3] == NOT_FOUND and re.search(r"\bsuccessor\b", sentences[sentence_index], re.IGNORECASE):
            later = next((e for e in events[index + 1:] if e[0] == "appointment" and e[3] != NOT_FOUND), None)
            if later:
                event[3] = later[3]
    return [tuple(event) for event in events]


def language_only_event_type(text):
    """Event type suggested by loose keywords when no person could be parsed, else None."""
    departure = bool(ANY_DEPARTURE_LANGUAGE.search(text))
    appointment = bool(ANY_APPOINTMENT_LANGUAGE.search(text))
    if departure and appointment:
        return "both"
    if departure:
        return "departure"
    if appointment:
        return "appointment"
    return None


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------
def make_row(company, filing, event):
    event_type, name, title, effective = event
    return {
        "company": company["company"], "ticker": company["ticker"], "cik": company["cik"],
        "filing_date": filing["filing_date"], "event_type": event_type,
        "person_name": name, "title": title, "effective_date": effective,
    }


def process_filing(company, filing):
    """Return (rows, skipped) for one Item 5.02 filing."""
    url = filing_folder(company["cik"], filing["accession"]) + filing["primary"]
    full_text = html_to_text(http_get(url).content)
    section = isolate_502_section(full_text)
    events = extract_events(section, filing["filing_date"]) if section else []

    # Fallback: the 5.02 section yielded no events and is either tiny or points at a press release.
    needs_press_release = not events and (
        len(section) < MIN_SECTION_CHARS or re.search(r"Exhibit\s+99|press\s+release", section, re.IGNORECASE)
    )
    if needs_press_release:
        try:
            press_url = find_press_release_url(company["cik"], filing["accession"])
            if press_url:
                press_text = html_to_text(http_get(press_url).content)
                events = events + extract_events(press_text[:6000], filing["filing_date"])
                section = section + " " + press_text[:6000]
            elif len(section) < MIN_SECTION_CHARS:
                print(f"  WARNING: {company['ticker']} {filing['filing_date']}: short/empty Item 5.02 text and no EX-99.1 found")
        except Exception as error:
            print(f"  WARNING: {company['ticker']} {filing['filing_date']}: could not read press release ({error})")

    if events:
        return [make_row(company, filing, e) for e in events], False

    event_type = language_only_event_type(section)
    if event_type:
        print(f"  WARNING: {company['ticker']} {filing['filing_date']}: departure/appointment language found "
              f"but no person could be parsed; saving a {event_type} row with NOT_FOUND fields")
        return [make_row(company, filing, (event_type, NOT_FOUND, NOT_FOUND, NOT_FOUND))], False
    print(f"{company['ticker']} | {filing['filing_date']} | Item 5.02 filing with no departure or appointment "
          f"(compensation or other) - skipped")
    return [], True


def main():
    cutoff = (date.today() - timedelta(days=LOOKBACK_DAYS)).isoformat()
    print(f"Looking for Item 5.02 filings from {cutoff} through {date.today().isoformat()}")

    rows = []
    filings_reviewed = filings_skipped = zero_event_companies = 0
    for company in COMPANIES:
        print(f"\n=== {company['company']} ({company['ticker']}) ===")
        try:
            filings = get_502_filings(company["cik"], cutoff)
        except Exception as error:
            print(f"  WARNING: {company['ticker']}: could not load filings list ({error}); skipping company")
            continue

        if not filings:
            print(f"{company['ticker']}: No executive events in past 12 months")
            zero_event_companies += 1
            continue

        for filing in filings:
            filings_reviewed += 1
            try:
                filing_rows, skipped = process_filing(company, filing)
            except Exception as error:
                print(f"  WARNING: {company['ticker']} {filing['filing_date']}: {error}")
                continue
            filings_skipped += int(skipped)
            for row in filing_rows:
                rows.append(row)
                print(f"{row['ticker']} | {row['filing_date']} | {row['event_type']} | "
                      f"{row['person_name']} | {row['title']}")

    with open(OUTPUT_PATH, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nItem 5.02 filings reviewed: {filings_reviewed}")
    print(f"Filings skipped (no departure or appointment): {filings_skipped}")
    print(f"Companies with zero Item 5.02 filings: {zero_event_companies}")
    print(f"Saved {len(rows)} events to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
