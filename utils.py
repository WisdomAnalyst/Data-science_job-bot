"""
utils.py — Shared helper functions for DS Job Bot.
Level detection, region detection, Nigeria-friendly scoring, date parsing, HTML cleaning.
"""

import re
import hashlib
from datetime import datetime, timedelta, timezone
from bs4 import BeautifulSoup

try:
    from dateutil import parser as dateutil_parser
except ImportError:
    dateutil_parser = None

# ── Data-science job title keywords ─────────────────────────────────────────
DS_KEYWORDS = [
    'data scientist', 'data science', 'machine learning', 'ml engineer',
    'ai engineer', 'deep learning', 'nlp engineer', 'computer vision',
    'applied scientist', 'research scientist', 'analytics engineer',
    'mlops engineer', 'ai researcher', 'quantitative analyst',
    'data analyst', 'business intelligence', 'bi engineer',
]

# ── Level patterns ───────────────────────────────────────────────────────────
JUNIOR_PATTERNS = [
    r'\bjunior\b', r'\bjr\.?\b', r'\bentry[\s\-]?level\b', r'\bassociate\b',
    r'\bgraduate\b', r'\btrainee\b', r'\bnew\s*grad\b', r'\b0[\s\-]2\s*years?\b',
    r'\b1[\s\-]2\s*years?\b',
]

SENIOR_PATTERNS = [
    r'\bsenior\b', r'\bsr\.?\b', r'\blead\b', r'\bprincipal\b',
    r'\bstaff\b', r'\bhead\s+of\b', r'\bdirector\b', r'\bvp\b',
    r'\b5\+\s*years?\b', r'\b7\+\s*years?\b', r'\b8\+\s*years?\b',
]

# ── Region keyword lists ─────────────────────────────────────────────────────
USA_KW = [
    'united states', ' usa ', 'u.s.a', 'u.s.', 'new york', 'san francisco',
    'seattle', 'chicago', 'austin', 'boston', 'los angeles', 'california',
    'texas', 'washington dc', 'new jersey', 'virginia', 'florida', 'georgia',
    'illinois', 'colorado', 'oregon', 'pennsylvania', 'ohio',
]
CANADA_KW = [
    'canada', 'toronto', 'vancouver', 'montreal', 'calgary', 'ottawa',
    'british columbia', 'ontario', 'alberta', 'quebec', 'edmonton',
]
UK_KW = [
    'united kingdom', ' uk ', 'u.k.', 'london', 'manchester', 'birmingham',
    'edinburgh', 'leeds', 'bristol', 'cambridge', 'oxford', 'england',
    'scotland', 'wales',
]
EU_KW = [
    'europe', 'european', 'germany', 'berlin', 'netherlands', 'amsterdam',
    'paris', 'france', 'sweden', 'stockholm', 'denmark', 'norway',
    'switzerland', 'zurich', 'ireland', 'dublin', 'spain', 'barcelona',
    'madrid', 'portugal', 'lisbon', 'poland', 'warsaw', 'czech', 'austria',
    'vienna', 'finland', 'helsinki', 'belgium', 'brussels', 'italy',
    'milan', 'rome', 'munich', 'hamburg', 'rotterdam',
]
WORLDWIDE_KW = [
    'worldwide', 'anywhere', 'global', 'all countries', 'open to all',
    'fully remote', 'remote worldwide', 'remote - anywhere',
    'work from anywhere', 'fully distributed', 'distributed team',
    'international',
]

# ── Nigeria-exclusion patterns ───────────────────────────────────────────────
NOT_NG_PATTERNS = [
    'must be authorized to work in', 'us citizens only', 'us citizen only',
    'security clearance', 'nato clearance', 'must have work authorization',
    'visa sponsorship not available', 'no visa sponsorship',
    'eu/eea only', 'must be based in', 'on-site only',
    'must be in office', 'requires relocation to',
    'right to work in the uk', 'right to work in the us',
    'only candidates in', 'residents only',
]


# ── Core helpers ─────────────────────────────────────────────────────────────

def strip_html(html_text) -> str:
    """Strip HTML tags from a string."""
    if not html_text:
        return ''
    soup = BeautifulSoup(str(html_text), 'lxml')
    return soup.get_text(separator=' ', strip=True)


def clean_description(text: str, max_length: int = 600) -> str:
    """Strip HTML, normalise whitespace, truncate."""
    text = strip_html(text)
    text = re.sub(r'\s+', ' ', text).strip()
    if len(text) > max_length:
        truncated = text[:max_length].rsplit(' ', 1)
        text = (truncated[0] if len(truncated[0]) > 0 else text[:max_length]) + '...'
    return text


def generate_id(source: str, raw_id: str) -> str:
    """Create a stable unique ID for a job."""
    key = f"{source}_{raw_id}"
    return hashlib.md5(key.encode()).hexdigest()[:16]


def detect_level(title: str, description: str = '') -> str:
    """Return 'Junior', 'Mid', or 'Senior' based on title/description."""
    text = f"{title} {description[:200]}".lower()
    for pat in SENIOR_PATTERNS:
        if re.search(pat, text):
            return 'Senior'
    for pat in JUNIOR_PATTERNS:
        if re.search(pat, text):
            return 'Junior'
    return 'Mid'


def detect_region(location: str) -> str:
    """Map a location string to a region bucket."""
    if not location:
        return 'Remote'
    loc = f" {location.lower()} "

    # Worldwide / fully-remote signals take priority over any country mention.
    for kw in WORLDWIDE_KW:
        if kw in loc:
            return 'Worldwide'
    if 'remote' in loc:
        return 'Remote'

    for kw in USA_KW:
        if kw in loc:
            return 'USA'
    for kw in CANADA_KW:
        if kw in loc:
            return 'Canada'
    for kw in UK_KW:
        if kw in loc:
            return 'UK'
    for kw in EU_KW:
        if kw in loc:
            return 'Europe'
    return 'Other'


def detect_nigeria_friendly(location: str, description: str = '') -> bool:
    """
    Return True if the role is plausibly open to Nigerian applicants.
    Logic:
      - Remote/worldwide jobs with no explicit country restrictions → True
      - Jobs mentioning Nigeria or Africa → True
      - Jobs with explicit country-lock language → False
    """
    loc_l = (location or '').lower()
    desc_l = (description or '').lower()
    combined = f"{loc_l} {desc_l}"

    # Hard exclusions
    for pat in NOT_NG_PATTERNS:
        if pat in combined:
            return False

    # Positive signals
    if 'nigeria' in combined or 'africa' in combined:
        return True
    for kw in WORLDWIDE_KW:
        if kw in combined:
            return True
    if 'remote' in loc_l:
        return True

    return False


def parse_date(date_str: str):
    """Parse a date string → timezone-aware datetime, or None."""
    if not date_str:
        return None
    if dateutil_parser:
        try:
            dt = dateutil_parser.parse(date_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except (ValueError, OverflowError):
            return None
    # Fallback: try common formats with their correct expected string lengths.
    for fmt, length in [('%Y-%m-%dT%H:%M:%SZ', 20), ('%Y-%m-%d', 10), ('%d/%m/%Y', 10)]:
        try:
            dt = datetime.strptime(date_str[:length], fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def is_within_days(dt, days: int = 7) -> bool:
    """Return True if dt is within the last N days."""
    if not dt:
        return True          # unknown date → include by default
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (now - dt).days <= days


def is_data_science_role(title: str, description: str = '') -> bool:
    """Return True if title/description matches a DS/ML/AI role."""
    text = f"{title} {description[:150]}".lower()
    return any(kw in text for kw in DS_KEYWORDS)
