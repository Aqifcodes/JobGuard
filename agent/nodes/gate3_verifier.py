"""
Gate 3: External Company + Recruiter + Domain Verification.

Purpose
-------
Gate 3 collects independent external identity and consistency evidence.

It does NOT make a final scam/legitimate decision.

Gate 3 investigates:

1. Company identity
   - Claimed company name
   - Company/domain consistency
   - Registry evidence state
   - MCA/Udyam availability state
   - Website identity evidence

2. Recruiter identity
   - Email provider
   - Corporate/custom domain
   - Company/domain consistency
   - Multiple email consistency

3. Domain / Website
   - DNS resolution
   - HTTPS reachability
   - Redirect destination
   - Website title/content identity
   - RDAP/domain registration information
   - Domain age when registration data is available

Important:
---------------
NOT_FOUND != FAKE
UNKNOWN != SCAM
GENERIC EMAIL != SCAM
DOMAIN UNREACHABLE != FAKE

Gate 5 receives the collected evidence and reasons over it.
"""

from __future__ import annotations

import re
import socket
import time
import urllib.parse
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

import httpx

from .input_processor import InvestigationInput


# ============================================================================
# DATA MODELS
# ============================================================================


class VerificationStatus(str, Enum):
    VERIFIED = "VERIFIED"
    SUSPICIOUS = "SUSPICIOUS"
    UNKNOWN = "UNKNOWN"
    ERROR = "ERROR"


@dataclass
class VerificationResult:
    status: VerificationStatus
    evidence: list[str] = field(default_factory=list)
    source: str = "Gate 3"
    confidence: Optional[float] = None
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "evidence": self.evidence,
            "source": self.source,
            "confidence": self.confidence,
            "warnings": self.warnings,
            "metadata": self.metadata,
        }


@dataclass
class Gate3Result:
    company_verification: VerificationResult
    recruiter_verification: VerificationResult
    domain_verification: VerificationResult

    def to_dict(self) -> dict[str, Any]:
        return {
            "company_verification": self.company_verification.to_dict(),
            "recruiter_verification": self.recruiter_verification.to_dict(),
            "domain_verification": self.domain_verification.to_dict(),
        }


# ============================================================================
# CONFIGURATION
# ============================================================================


GENERIC_EMAIL_PROVIDERS = {
    "gmail.com",
    "googlemail.com",
    "yahoo.com",
    "yahoo.co.in",
    "hotmail.com",
    "outlook.com",
    "outlook.in",
    "live.com",
    "rediffmail.com",
    "icloud.com",
    "protonmail.com",
    "proton.me",
}

HTTP_TIMEOUT_SECONDS = 7.0

MAX_WEBSITE_TEXT_LENGTH = 5000

USER_AGENT = (
    "Mozilla/5.0 "
    "(Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 "
    "(KHTML, like Gecko) "
    "Chrome/151.0 Safari/537.36 "
    "JobScamDetector/1.0"
)


# ============================================================================
# GENERAL HELPERS
# ============================================================================


def _safe_lower(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().lower()


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []

    for value in values:
        value = str(value).strip()

        if not value:
            continue

        key = value.lower()

        if key not in seen:
            seen.add(key)
            result.append(value)

    return result


def _extract_domain_from_email(email: str) -> Optional[str]:
    """
    Extract the domain from an email address.
    """
    email = email.strip().lower()

    if "@" not in email:
        return None

    local, domain = email.rsplit("@", 1)

    if not local or not domain:
        return None

    domain = domain.strip().strip(".")

    if not domain:
        return None

    return domain


def _extract_domain_from_url(url: str) -> Optional[str]:
    """
    Extract hostname from a URL.
    Handles URLs that do not explicitly contain a scheme.
    """
    try:
        url = url.strip()

        if not url:
            return None

        if "://" not in url:
            url = "https://" + url

        parsed = urllib.parse.urlparse(url)

        hostname = parsed.hostname

        if hostname:
            return hostname.lower().strip(".")

    except Exception:
        pass

    return None


def _get_all_domains(
    investigation_input: InvestigationInput,
) -> list[str]:
    """
    Collect unique domains from:

    - recruiter emails
    - supplied URLs
    """
    domains: set[str] = set()

    for email in investigation_input.email_addresses:
        domain = _extract_domain_from_email(email)

        if domain:
            domains.add(domain)

    for url in investigation_input.urls:
        domain = _extract_domain_from_url(url)

        if domain:
            domains.add(domain)

    return sorted(domains)


# ============================================================================
# COMPANY NAME NORMALIZATION
# ============================================================================


def _normalize_company_name(name: str) -> str:
    """
    Normalize a company name for identity comparison.

    This is normalization, NOT a fraud rule.
    """

    name = _safe_lower(name)

    # Remove punctuation.
    name = re.sub(r"[^a-z0-9\s]", " ", name)

    # Common legal entity suffixes.
    suffixes = [
        "private limited",
        "pvt ltd",
        "pvt limited",
        "public limited",
        "limited",
        "ltd",
        "llp",
        "llc",
        "incorporated",
        "inc",
        "corp",
        "corporation",
        "company",
        "co",
    ]

    for suffix in suffixes:
        name = re.sub(
            rf"\b{re.escape(suffix)}\b",
            " ",
            name,
        )

    name = re.sub(r"\s+", " ", name).strip()

    return name.replace(" ", "")


def _company_tokens(name: str) -> set[str]:
    normalized = _safe_lower(name)

    normalized = re.sub(
        r"[^a-z0-9\s]",
        " ",
        normalized,
    )

    return {
        token
        for token in normalized.split()
        if len(token) >= 3
    }


def _domain_core(domain: str) -> str:
    """
    Extract the registrable-looking core from a domain.

    Example:
        careers.example.in -> example

    This is intentionally simple and used only for consistency evidence.
    """
    domain = domain.lower().strip(".")

    parts = domain.split(".")

    if len(parts) >= 2:
        # Common second-level country domains.
        if parts[-2] in {
            "co",
            "com",
            "net",
            "org",
            "gov",
            "edu",
        } and len(parts) >= 3:
            return parts[-3]

        return parts[-2]

    return parts[0] if parts else ""


def _company_domain_match(
    company_name: str,
    domain: str,
) -> str:
    """
    Compare claimed company identity with domain identity.

    Returns:
        MATCH
        MISMATCH
        UNKNOWN

    This is NOT a final fraud rule.
    """

    if not company_name or not domain:
        return "UNKNOWN"

    normalized_company = _normalize_company_name(company_name)
    core = _domain_core(domain)

    if not normalized_company or not core:
        return "UNKNOWN"

    company_tokens = _company_tokens(company_name)

    if normalized_company in core:
        return "MATCH"

    if core in normalized_company:
        return "MATCH"

    # Token-level comparison.
    domain_tokens = set(
        re.findall(
            r"[a-z0-9]+",
            core.lower(),
        )
    )

    if company_tokens & domain_tokens:
        return "MATCH"

    return "MISMATCH"


# ============================================================================
# WEBSITE INVESTIGATION
# ============================================================================


def _fetch_website(
    domain: str,
) -> dict[str, Any]:
    """
    Fetch a website and collect basic identity evidence.

    No verdict is produced here.
    """

    result: dict[str, Any] = {
        "domain": domain,
        "https_reachable": False,
        "http_status": None,
        "final_url": None,
        "redirected": False,
        "title": None,
        "text_sample": None,
        "content_length": None,
        "error": None,
    }

    url = f"https://{domain}"

    try:
        with httpx.Client(
            timeout=HTTP_TIMEOUT_SECONDS,
            follow_redirects=True,
            verify=False,
            headers={"User-Agent": USER_AGENT},
        ) as client:

            response = client.get(url)

            result["http_status"] = response.status_code
            result["final_url"] = str(response.url)

            result["redirected"] = (
                str(response.url).rstrip("/")
                != url.rstrip("/")
            )

            if response.status_code < 400:
                result["https_reachable"] = True

            content_type = response.headers.get(
                "content-type",
                "",
            ).lower()

            if "text/html" in content_type:
                html = response.text

                result["content_length"] = len(html)

                # Extract title.
                title_match = re.search(
                    r"<title[^>]*>(.*?)</title>",
                    html,
                    flags=re.IGNORECASE | re.DOTALL,
                )

                if title_match:
                    title = re.sub(
                        r"\s+",
                        " ",
                        title_match.group(1),
                    ).strip()

                    result["title"] = title[:500]

                # Remove scripts/styles.
                cleaned = re.sub(
                    r"<script.*?</script>",
                    " ",
                    html,
                    flags=re.IGNORECASE | re.DOTALL,
                )

                cleaned = re.sub(
                    r"<style.*?</style>",
                    " ",
                    cleaned,
                    flags=re.IGNORECASE | re.DOTALL,
                )

                cleaned = re.sub(
                    r"<[^>]+>",
                    " ",
                    cleaned,
                )

                cleaned = re.sub(
                    r"\s+",
                    " ",
                    cleaned,
                ).strip()

                result["text_sample"] = (
                    cleaned[:MAX_WEBSITE_TEXT_LENGTH]
                )

    except httpx.RequestError as exc:
        result["error"] = type(exc).__name__

    except Exception as exc:
        result["error"] = type(exc).__name__

    return result


# ============================================================================
# RDAP / DOMAIN REGISTRATION INVESTIGATION
# ============================================================================


def _get_rdap_bootstrap() -> dict[str, Any]:
    """
    Fetch IANA RDAP bootstrap information.

    This avoids hardcoding one registry server.
    """

    url = "https://data.iana.org/rdap/dns.json"

    try:
        with httpx.Client(
            timeout=HTTP_TIMEOUT_SECONDS,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        ) as client:

            response = client.get(url)
            response.raise_for_status()

            return response.json()

    except Exception:
        return {}


def _find_rdap_server(
    domain: str,
) -> Optional[str]:
    """
    Find the RDAP service responsible for the domain TLD.
    """

    parts = domain.lower().strip(".").split(".")

    if not parts:
        return None

    tld = parts[-1]

    bootstrap = _get_rdap_bootstrap()

    services = bootstrap.get("services", [])

    for service in services:
        if not isinstance(service, list) or len(service) != 2:
            continue

        tlds, urls = service

        if tld in tlds and urls:
            return urls[0]

    return None


def _parse_rdap_event_date(
    event: dict[str, Any],
) -> Optional[str]:
    date_value = event.get("eventDate")

    if not date_value:
        return None

    return str(date_value)


def _calculate_domain_age_days(
    registration_date: Optional[str],
) -> Optional[int]:
    if not registration_date:
        return None

    try:
        registration = datetime.fromisoformat(
            registration_date.replace("Z", "+00:00")
        )

        if registration.tzinfo is None:
            registration = registration.replace(
                tzinfo=timezone.utc
            )

        now = datetime.now(timezone.utc)

        age = now - registration

        return max(0, age.days)

    except Exception:
        return None


def _fetch_rdap(
    domain: str,
) -> dict[str, Any]:
    """
    Query RDAP for domain registration information.

    RDAP availability varies by TLD, so failure becomes UNKNOWN evidence.
    """

    result: dict[str, Any] = {
        "available": False,
        "domain": domain,
        "rdap_server": None,
        "registration_date": None,
        "expiration_date": None,
        "domain_age_days": None,
        "status": [],
        "error": None,
    }

    server = _find_rdap_server(domain)

    if not server:
        result["error"] = "RDAP server not found"
        return result

    result["rdap_server"] = server

    url = server.rstrip("/") + "/domain/" + domain

    try:
        with httpx.Client(
            timeout=HTTP_TIMEOUT_SECONDS,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        ) as client:

            response = client.get(url)

            if response.status_code == 404:
                result["error"] = "DOMAIN_NOT_FOUND"
                return result

            response.raise_for_status()

            data = response.json()

            result["available"] = True

            result["status"] = data.get(
                "status",
                [],
            )

            registration_date = None
            expiration_date = None

            for event in data.get("events", []):
                if not isinstance(event, dict):
                    continue

                action = _safe_lower(
                    event.get("eventAction")
                )

                event_date = _parse_rdap_event_date(event)

                if action == "registration":
                    registration_date = event_date

                elif action == "expiration":
                    expiration_date = event_date

            result["registration_date"] = registration_date
            result["expiration_date"] = expiration_date

            result["domain_age_days"] = (
                _calculate_domain_age_days(
                    registration_date
                )
            )

    except httpx.RequestError as exc:
        result["error"] = type(exc).__name__

    except Exception as exc:
        result["error"] = type(exc).__name__

    return result


# ============================================================================
# COMPANY VERIFICATION
# ============================================================================


def _company_registry_evidence(
    company_name: str,
) -> dict[str, Any]:
    """
    Describe registry verification availability.

    Important:
    We intentionally do not pretend that MCA/Udyam can be queried through
    a generic public API.

    A missing automated registry result is therefore UNKNOWN.

    This keeps the system honest and prevents:
        MCA_NOT_FOUND -> SCAM
    """

    return {
        "mca": {
            "status": "UNKNOWN",
            "reason": (
                "Automated MCA registry verification is not "
                "available through a guaranteed public API."
            ),
        },
        "udyam": {
            "status": "UNKNOWN",
            "reason": (
                "Automated Udyam/MSME verification is not "
                "available through a guaranteed public API."
            ),
        },
        "claimed_company": company_name,
    }


def _verify_company(
    investigation_input: InvestigationInput,
    domains: list[str],
    website_results: dict[str, dict[str, Any]],
) -> VerificationResult:

    if not investigation_input.company_names:

        return VerificationResult(
            status=VerificationStatus.UNKNOWN,
            evidence=[
                "No company name was found in the input."
            ],
            warnings=[
                "Company identity cannot be independently compared "
                "without a claimed company name."
            ],
            metadata={
                "missing_company": True,
            },
        )

    company_names = _unique(
        investigation_input.company_names
    )

    primary_company = company_names[0]

    normalized_company = _normalize_company_name(
        primary_company
    )

    evidence: list[str] = [
        f"Claimed company: {primary_company}"
    ]

    warnings: list[str] = []

    metadata: dict[str, Any] = {
        "primary_company": primary_company,
        "company_names_found": company_names,
        "normalized_company": normalized_company,
        "registry_checks": _company_registry_evidence(
            primary_company
        ),
        "domain_identity_checks": {},
        "website_identity_checks": {},
    }

    match_count = 0
    mismatch_count = 0

    # ------------------------------------------------------------------
    # Company <-> Domain identity
    # ------------------------------------------------------------------

    for domain in domains:

        if domain in GENERIC_EMAIL_PROVIDERS:
            continue

        relationship = _company_domain_match(
            primary_company,
            domain,
        )

        metadata["domain_identity_checks"][
            domain
        ] = relationship

        if relationship == "MATCH":

            match_count += 1

            evidence.append(
                f"Company identity is consistent with domain: {domain}"
            )

        elif relationship == "MISMATCH":

            mismatch_count += 1

            evidence.append(
                f"Company identity does not clearly match domain: {domain}"
            )

    # ------------------------------------------------------------------
    # Website identity
    # ------------------------------------------------------------------

    company_tokens = _company_tokens(
        primary_company
    )

    for domain, website in website_results.items():

        title = website.get("title") or ""
        text = website.get("text_sample") or ""

        combined = f"{title} {text}".lower()

        website_tokens = set(
            re.findall(
                r"[a-z0-9]+",
                combined,
            )
        )

        overlap = company_tokens & website_tokens

        identity_match = bool(overlap)

        metadata["website_identity_checks"][
            domain
        ] = {
            "title": title,
            "identity_token_overlap": sorted(
                overlap
            ),
            "identity_match": identity_match,
        }

        if identity_match:

            evidence.append(
                f"Website content contains terms consistent "
                f"with the claimed company: {domain}"
            )

        elif website.get("https_reachable"):

            evidence.append(
                f"Website is reachable, but its visible content "
                f"does not clearly identify the claimed company: {domain}"
            )

    # ------------------------------------------------------------------
    # Registry explanation
    # ------------------------------------------------------------------

    evidence.append(
        "MCA/Udyam automated registry status is UNKNOWN because "
        "no guaranteed public API was used."
    )

    warnings.append(
        "Registry absence has not been treated as evidence of fraud."
    )

    # ------------------------------------------------------------------
    # Determine Gate 3 company evidence status
    # ------------------------------------------------------------------

    if match_count > 0 and mismatch_count == 0:

        status = VerificationStatus.VERIFIED

        confidence = 0.75

    elif mismatch_count > 0 and match_count == 0:

        status = VerificationStatus.SUSPICIOUS

        confidence = 0.65

    elif match_count > 0 and mismatch_count > 0:

        status = VerificationStatus.SUSPICIOUS

        confidence = 0.55

        warnings.append(
            "Different domains produced mixed company identity evidence."
        )

    else:

        status = VerificationStatus.UNKNOWN

        confidence = None

    return VerificationResult(
        status=status,
        evidence=evidence,
        confidence=confidence,
        warnings=warnings,
        metadata=metadata,
    )


# ============================================================================
# RECRUITER VERIFICATION
# ============================================================================


def _verify_recruiter(
    investigation_input: InvestigationInput,
    company_result: VerificationResult,
) -> VerificationResult:

    emails = _unique(
        investigation_input.email_addresses
    )

    if not emails:

        return VerificationResult(
            status=VerificationStatus.UNKNOWN,
            evidence=[
                "No recruiter email addresses were found."
            ],
            warnings=[
                "Recruiter identity could not be evaluated "
                "without an email address."
            ],
            metadata={
                "missing_email": True,
            },
        )

    claimed_company = company_result.metadata.get(
        "primary_company"
    )

    evidence: list[str] = []
    warnings: list[str] = []

    metadata: dict[str, Any] = {
        "emails": emails,
        "generic_provider_used": False,
        "corporate_email_used": False,
        "email_checks": {},
    }

    matching_domains = 0
    mismatching_domains = 0

    for email in emails:

        domain = _extract_domain_from_email(email)

        if not domain:

            evidence.append(
                f"Email address could not be parsed: {email}"
            )

            metadata["email_checks"][email] = {
                "valid_domain": False,
            }

            continue

        is_generic = (
            domain in GENERIC_EMAIL_PROVIDERS
        )

        company_relationship = (
            _company_domain_match(
                claimed_company or "",
                domain,
            )
        )

        metadata["email_checks"][email] = {
            "domain": domain,
            "generic_provider": is_generic,
            "company_domain_relationship": (
                company_relationship
            ),
        }

        evidence.append(
            f"Recruiter email found: {email}"
        )

        if is_generic:

            metadata["generic_provider_used"] = True

            evidence.append(
                f"{email} uses a generic email provider: {domain}"
            )

            warnings.append(
                "A generic email provider does not by itself "
                "establish that the recruiter is fraudulent."
            )

        else:

            metadata["corporate_email_used"] = True

            evidence.append(
                f"{email} uses a custom domain: {domain}"
            )

            if company_relationship == "MATCH":

                matching_domains += 1

                evidence.append(
                    f"Recruiter email domain is consistent "
                    f"with the claimed company: {claimed_company}"
                )

            elif company_relationship == "MISMATCH":

                mismatching_domains += 1

                evidence.append(
                    f"Recruiter email domain does not clearly "
                    f"match the claimed company: {claimed_company}"
                )

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    if matching_domains > 0 and mismatching_domains == 0:

        status = VerificationStatus.VERIFIED
        confidence = 0.80

    elif mismatching_domains > 0:

        status = VerificationStatus.SUSPICIOUS
        confidence = 0.70

    elif metadata["generic_provider_used"]:

        # Generic provider alone is insufficient for a fraud conclusion.
        status = VerificationStatus.UNKNOWN
        confidence = None

    else:

        status = VerificationStatus.UNKNOWN
        confidence = None

    return VerificationResult(
        status=status,
        evidence=evidence,
        confidence=confidence,
        warnings=_unique(warnings),
        metadata=metadata,
    )


# ============================================================================
# DOMAIN VERIFICATION
# ============================================================================


def _verify_domain(
    domains: list[str],
    website_results: dict[str, dict[str, Any]],
    rdap_results: dict[str, dict[str, Any]],
) -> VerificationResult:

    if not domains:

        return VerificationResult(
            status=VerificationStatus.UNKNOWN,
            evidence=[
                "No domains were found to investigate."
            ],
            metadata={
                "domains": [],
            },
        )

    evidence: list[str] = []
    warnings: list[str] = []

    metadata: dict[str, Any] = {
        "domains": domains,
        "domain_checks": {},
    }

    resolving_domains = 0
    reachable_domains = 0
    failed_domains = 0

    for domain in domains:

        domain_data: dict[str, Any] = {
            "dns": {},
            "website": website_results.get(
                domain,
                {},
            ),
            "rdap": rdap_results.get(
                domain,
                {},
            ),
        }

        # --------------------------------------------------------------
        # Generic providers
        # --------------------------------------------------------------

        if domain in GENERIC_EMAIL_PROVIDERS:

            evidence.append(
                f"{domain} is a generic email provider."
            )

            metadata["domain_checks"][
                domain
            ] = domain_data

            continue

        evidence.append(
            f"Investigating domain: {domain}"
        )

        # --------------------------------------------------------------
        # DNS
        # --------------------------------------------------------------

        try:

            addresses = socket.getaddrinfo(
                domain,
                443,
                type=socket.SOCK_STREAM,
            )

            ips = sorted(
                {
                    item[4][0]
                    for item in addresses
                    if item[4]
                }
            )

            if ips:

                resolving_domains += 1

                domain_data["dns"] = {
                    "resolves": True,
                    "addresses": ips,
                }

                evidence.append(
                    f"Domain {domain} resolves through DNS."
                )

            else:

                failed_domains += 1

                domain_data["dns"] = {
                    "resolves": False,
                    "addresses": [],
                }

                evidence.append(
                    f"Domain {domain} returned no usable DNS addresses."
                )

        except socket.gaierror:

            failed_domains += 1

            domain_data["dns"] = {
                "resolves": False,
                "addresses": [],
            }

            evidence.append(
                f"DNS resolution failed for {domain}."
            )

        except Exception as exc:

            domain_data["dns"] = {
                "resolves": None,
                "error": type(exc).__name__,
            }

            warnings.append(
                f"DNS investigation for {domain} encountered "
                f"{type(exc).__name__}."
            )

        # --------------------------------------------------------------
        # Website
        # --------------------------------------------------------------

        website = website_results.get(
            domain,
            {},
        )

        if website.get("https_reachable"):

            reachable_domains += 1

            evidence.append(
                f"HTTPS website for {domain} is reachable."
            )

            if website.get("redirected"):

                evidence.append(
                    f"{domain} redirects to "
                    f"{website.get('final_url')}."
                )

            if website.get("title"):

                evidence.append(
                    f"Website title: {website['title']}"
                )

        elif website.get("error"):

            evidence.append(
                f"HTTPS investigation for {domain} "
                f"returned {website['error']}."
            )

            failed_domains += 1

        # --------------------------------------------------------------
        # RDAP
        # --------------------------------------------------------------

        rdap = rdap_results.get(
            domain,
            {},
        )

        if rdap.get("available"):

            registration_date = rdap.get(
                "registration_date"
            )

            domain_age_days = rdap.get(
                "domain_age_days"
            )

            if registration_date:

                evidence.append(
                    f"RDAP registration date for {domain}: "
                    f"{registration_date}"
                )

            if domain_age_days is not None:

                evidence.append(
                    f"RDAP-estimated domain age: "
                    f"{domain_age_days} days."
                )

        elif rdap.get("error"):

            warnings.append(
                f"RDAP information for {domain} "
                f"is unavailable: {rdap['error']}."
            )

        metadata["domain_checks"][
            domain
        ] = domain_data

    # ----------------------------------------------------------------------
    # Overall status
    # ----------------------------------------------------------------------

    non_generic_domains = [
        domain
        for domain in domains
        if domain not in GENERIC_EMAIL_PROVIDERS
    ]

    if not non_generic_domains:

        return VerificationResult(
            status=VerificationStatus.UNKNOWN,
            evidence=evidence,
            warnings=[
                "Only generic email-provider domains were found."
            ],
            metadata=metadata,
        )

    if reachable_domains > 0 and failed_domains == 0:

        status = VerificationStatus.VERIFIED
        confidence = 0.75

    elif reachable_domains > 0 and failed_domains > 0:

        status = VerificationStatus.SUSPICIOUS
        confidence = 0.50

        warnings.append(
            "Some domains were reachable while others failed "
            "technical checks."
        )

    elif resolving_domains > 0 and reachable_domains == 0:

        # Domain exists technically but website may be unavailable.
        status = VerificationStatus.UNKNOWN
        confidence = None

        warnings.append(
            "DNS exists, but website reachability could not be "
            "established. This does not prove the domain is fraudulent."
        )

    else:

        status = VerificationStatus.SUSPICIOUS
        confidence = 0.60

    return VerificationResult(
        status=status,
        evidence=evidence,
        confidence=confidence,
        warnings=_unique(warnings),
        metadata=metadata,
    )


# ============================================================================
# MAIN GATE 3 PIPELINE
# ============================================================================


def verify_company_recruiter_domain(
    investigation_input: InvestigationInput,
) -> Gate3Result:
    """
    Perform Gate 3 external verification.

    Execution order:

        1. Extract domains
        2. Investigate websites
        3. Investigate RDAP/domain registration
        4. Verify company identity
        5. Verify recruiter identity
        6. Verify domain technical evidence
        7. Return structured evidence

    Gate 3 does not produce a final scam/legitimate verdict.
    """

    domains = _get_all_domains(
        investigation_input
    )

    # ----------------------------------------------------------------------
    # External website investigation
    # ----------------------------------------------------------------------

    website_results: dict[str, dict[str, Any]] = {}

    for domain in domains:

        if domain in GENERIC_EMAIL_PROVIDERS:
            continue

        website_results[domain] = _fetch_website(
            domain
        )

        # Small delay prevents unnecessarily aggressive requests.
        time.sleep(0.05)

    # ----------------------------------------------------------------------
    # Domain registration investigation
    # ----------------------------------------------------------------------

    rdap_results: dict[str, dict[str, Any]] = {}

    for domain in domains:

        if domain in GENERIC_EMAIL_PROVIDERS:
            continue

        rdap_results[domain] = _fetch_rdap(
            domain
        )

    # ----------------------------------------------------------------------
    # Company
    # ----------------------------------------------------------------------

    company_verification = _verify_company(
        investigation_input=investigation_input,
        domains=domains,
        website_results=website_results,
    )

    # ----------------------------------------------------------------------
    # Recruiter
    # ----------------------------------------------------------------------

    recruiter_verification = _verify_recruiter(
        investigation_input=investigation_input,
        company_result=company_verification,
    )

    # ----------------------------------------------------------------------
    # Domain
    # ----------------------------------------------------------------------

    domain_verification = _verify_domain(
        domains=domains,
        website_results=website_results,
        rdap_results=rdap_results,
    )

    return Gate3Result(
        company_verification=company_verification,
        recruiter_verification=recruiter_verification,
        domain_verification=domain_verification,
    )


# ============================================================================
# PUBLIC API
# ============================================================================


__all__ = [
    "VerificationStatus",
    "VerificationResult",
    "Gate3Result",
    "verify_company_recruiter_domain",
]

