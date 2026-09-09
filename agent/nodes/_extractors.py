"""Deterministic, regex-based entity extraction utilities.

These extractors are intentionally simple and rule-based. They are used to
surface *mentions* of entities (e.g. a company name appearing in a job post).
They do NOT verify, validate, or make any claim about the legitimacy of the
extracted entities. Verification is a separate, later stage of the pipeline.
"""

from __future__ import annotations

import re
from typing import Iterable

# ---------------------------------------------------------------------------
# URL extraction
# ---------------------------------------------------------------------------

_URL_RE = re.compile(r"(?i)\b(?:https?://|www\.)[^\s<>\"']+")

# ---------------------------------------------------------------------------
# Email extraction
# ---------------------------------------------------------------------------

_EMAIL_RE = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")

# ---------------------------------------------------------------------------
# Indian phone number extraction
# ---------------------------------------------------------------------------

# Matches common Indian phone formats:
#   +91 98765 43210 | +91-98765-43210 | 98765 43210 | 098765 43210
#   9876543210 | 09876543210 | +91 9876543210 | (91) 98765 43210
_PHONE_RE = re.compile(
    r"(?<!\d)"
    r"(?:\+?91[\s.-]?)?"
    r"(?:0)?"
    r"[6-9]\d{4}[\s.-]?\d{5}"
    r"(?!\d)"
)

# ---------------------------------------------------------------------------
# Salary extraction (Indian Rupees)
# ---------------------------------------------------------------------------

_SALARY_RE = re.compile(
    r"(?i)"
    r"(?:₹|rs\.?|inr|rupees?)\s*"
    r"([\d,]+(?:\.\d+)?)\s*"
    r"(lakh|lpa|lacs?|crore|k|thousand|per\s*(?:annum|year|month)|"
    r"/?\s*(?:annum|year|month|yr))?"
)

# ---------------------------------------------------------------------------
# Company name extraction (heuristic)
# ---------------------------------------------------------------------------

# Matches a company name that follows an explicit keyword (e.g. "Company:")
# and ends in a common corporate suffix. The suffix is included in the
# captured name. Greedy matching captures the full name (e.g.
# "Acme Technologies Pvt Ltd").
_COMPANY_RE = re.compile(
    r"(?i)(?:company|organization|firm|employer)\s*[:\-]?\s*"
    r"([A-Z][A-Z0-9&.\- ]{1,60}"
    r"(?:inc\.?|llc|ltd\.?|limited|corp\.?|corporation|"
    r"pvt\.?\s*ltd\.?|private\s+limited|technologies?|tech|"
    r"systems?|solutions?|services?|consulting|group|"
    r"labs?|softwares?|digital|ventures|industries?))\b"
)

# ---------------------------------------------------------------------------
# Person name extraction (heuristic)
# ---------------------------------------------------------------------------

# Matches "First Last" or "First M. Last" capitalized name patterns, often
# preceded by a role keyword like "Hiring Manager" or "Recruiter".
# A negative lookahead prevents common field labels (Email, Phone, etc.)
# from being captured as part of the name.
_NAME_RE = re.compile(
    r"(?i)\b(?:hiring\s+manager|recruiter|contact|"
    r"talent\s+acquisition|hr|point\s+of\s+contact)\s*[:\-]?\s*"
    r"([A-Z][a-z]+(?:\s+(?!email|phone|location|salary|company|"
    r"job|position|title)[A-Z][a-z]+){1,3})"
)

# ---------------------------------------------------------------------------
# Job title extraction (heuristic)
# ---------------------------------------------------------------------------

_JOB_TITLE_RE = re.compile(
    r"(?i)\b(?:position|role|job\s+title|designation|"
    r"opening|vacancy)\s*[:\-]?\s*"
    r"([A-Za-z][A-Za-z0-9&.\- ]{2,60}?)"
    r"(?=\s*(?:location|salary|experience|qualification|"
    r"responsibilities|requirements|about|company|$))"
)

# ---------------------------------------------------------------------------
# Location extraction (heuristic)
# ---------------------------------------------------------------------------

_LOCATION_RE = re.compile(
    r"(?i)\b(?:location|based\s+in|work\s+from|office\s+at)\s*[:\-]?\s*"
    r"([A-Za-z][A-Za-z\s,.\-]{2,60}?)"
    r"(?=\s*(?:salary|experience|qualification|responsibilities|"
    r"requirements|about|$))"
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _dedupe(items: Iterable[str]) -> list[str]:
    """Return unique items preserving first-seen order."""
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        item = item.strip()
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result


def extract_urls(text: str) -> list[str]:
    """Extract and normalize URLs from text."""
    urls = []
    for match in _URL_RE.findall(text):
        url = match.rstrip(".,;:!?)]}>\"'")
        if url.startswith("www."):
            url = "http://" + url
        urls.append(url)
    return _dedupe(urls)


def extract_emails(text: str) -> list[str]:
    """Extract email addresses from text."""
    return _dedupe(_EMAIL_RE.findall(text))


def extract_phone_numbers(text: str) -> list[str]:
    """Extract Indian phone numbers from text."""
    return _dedupe(_PHONE_RE.findall(text))


def extract_salaries(text: str) -> list[str]:
    """Extract salary mentions (Indian Rupees) from text."""
    salaries = []
    for match in _SALARY_RE.findall(text):
        amount, unit = match
        salaries.append(f"{amount} {unit}".strip())
    return _dedupe(salaries)


def extract_company_names(text: str) -> list[str]:
    """Extract heuristic company-name mentions from text."""
    return _dedupe(m.group(1).strip() for m in _COMPANY_RE.finditer(text))


def extract_recruiter_names(text: str) -> list[str]:
    """Extract heuristic recruiter/person-name mentions from text."""
    return _dedupe(m.group(1).strip() for m in _NAME_RE.finditer(text))


def extract_job_titles(text: str) -> list[str]:
    """Extract heuristic job-title mentions from text."""
    return _dedupe(m.group(1).strip() for m in _JOB_TITLE_RE.finditer(text))


def extract_locations(text: str) -> list[str]:
    """Extract heuristic location mentions from text."""
    return _dedupe(m.group(1).strip() for m in _LOCATION_RE.finditer(text))


def extract_all(text: str) -> dict[str, list[str]]:
    """Run all extractors and return a dict of entity -> list of mentions."""
    return {
        "urls": extract_urls(text),
        "email_addresses": extract_emails(text),
        "phone_numbers": extract_phone_numbers(text),
        "salary_mentions": extract_salaries(text),
        "company_names": extract_company_names(text),
        "recruiter_names": extract_recruiter_names(text),
        "job_titles": extract_job_titles(text),
        "locations": extract_locations(text),
    }
