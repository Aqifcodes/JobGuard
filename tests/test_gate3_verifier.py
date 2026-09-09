import socket
from unittest.mock import patch

import pytest

from agent.nodes.input_processor import InvestigationInput, SourceType
from agent.nodes.gate3_verifier import (
    verify_company_recruiter_domain,
    VerificationStatus,
    _extract_domain_from_email,
    _extract_domain_from_url,
    _normalize_company_name,
    _company_domain_match,
)


# ============================================================================
# HELPERS
# ============================================================================


def create_input(
    company_names=None,
    email_addresses=None,
    urls=None,
) -> InvestigationInput:

    return InvestigationInput(
        source_type=SourceType.TEXT,
        raw_text="",
        extracted_text="",
        company_names=company_names or [],
        email_addresses=email_addresses or [],
        urls=urls or [],
    )


def website_result(
    domain,
    reachable=True,
    status_code=200,
    title=None,
    text_sample=None,
    redirected=False,
    final_url=None,
    error=None,
):
    return {
        "domain": domain,
        "https_reachable": reachable,
        "http_status": status_code,
        "final_url": final_url or f"https://{domain}",
        "redirected": redirected,
        "title": title,
        "text_sample": text_sample,
        "content_length": 1000 if reachable else None,
        "error": error,
    }


def rdap_result(
    domain,
    available=True,
    registration_date="2020-01-01T00:00:00Z",
    domain_age_days=2400,
    error=None,
):
    return {
        "available": available,
        "domain": domain,
        "rdap_server": "https://rdap.example.com",
        "registration_date": registration_date,
        "expiration_date": None,
        "domain_age_days": domain_age_days,
        "status": ["active"],
        "error": error,
    }


# ============================================================================
# BASIC HELPER TESTS
# ============================================================================


def test_extract_domain_from_email():
    assert (
        _extract_domain_from_email("HR@Infosys.com")
        == "infosys.com"
    )


def test_extract_domain_from_invalid_email():
    assert _extract_domain_from_email("invalid-email") is None


def test_extract_domain_from_url():
    assert (
        _extract_domain_from_url(
            "https://www.infosys.com/careers"
        )
        == "www.infosys.com"
    )


def test_extract_domain_without_scheme():
    assert (
        _extract_domain_from_url("infosys.com/careers")
        == "infosys.com"
    )


def test_extract_domain_from_invalid_url():
    assert _extract_domain_from_url("") is None


def test_company_name_normalization():
    assert (
        _normalize_company_name("Infosys Limited")
        == "infosys"
    )

    assert (
        _normalize_company_name("Infosys Pvt Ltd")
        == "infosys"
    )


def test_company_domain_match():
    assert (
        _company_domain_match(
            "Infosys Limited",
            "infosys.com",
        )
        == "MATCH"
    )


def test_company_domain_mismatch():
    assert (
        _company_domain_match(
            "Infosys Limited",
            "randomcompany.com",
        )
        == "MISMATCH"
    )


# ============================================================================
# 1. VALID COMPANY + CORPORATE EMAIL + WEBSITE
# ============================================================================


@patch("agent.nodes.gate3_verifier._fetch_rdap")
@patch("agent.nodes.gate3_verifier._fetch_website")
@patch("socket.getaddrinfo")
def test_valid_company_and_recruiter(
    mock_dns,
    mock_website,
    mock_rdap,
):

    mock_dns.return_value = [
        (
            socket.AF_INET,
            socket.SOCK_STREAM,
            6,
            "",
            ("1.2.3.4", 443),
        )
    ]

    mock_website.return_value = website_result(
        "infosys.com",
        reachable=True,
        status_code=200,
        title="Infosys Careers",
        text_sample=(
            "Infosys Limited careers jobs opportunities"
        ),
    )

    mock_rdap.return_value = rdap_result(
        "infosys.com"
    )

    inp = create_input(
        company_names=["Infosys Limited"],
        email_addresses=["hr@infosys.com"],
        urls=["https://infosys.com/careers"],
    )

    result = verify_company_recruiter_domain(inp)

    assert (
        result.company_verification.status
        == VerificationStatus.VERIFIED
    )

    assert (
        result.recruiter_verification.status
        == VerificationStatus.VERIFIED
    )

    assert (
        result.domain_verification.status
        == VerificationStatus.VERIFIED
    )


# ============================================================================
# 2. GENERIC GMAIL RECRUITER
# ============================================================================


def test_generic_gmail_recruiter():

    inp = create_input(
        company_names=["TCS"],
        email_addresses=["tcs.recruitment@gmail.com"],
    )

    result = verify_company_recruiter_domain(inp)

    # IMPORTANT:
    # Generic email alone is NOT treated as fraud.
    assert (
        result.recruiter_verification.status
        == VerificationStatus.UNKNOWN
    )

    assert (
        result.recruiter_verification.metadata[
            "generic_provider_used"
        ]
        is True
    )

    assert (
        result.recruiter_verification.metadata[
            "corporate_email_used"
        ]
        is False
    )


# ============================================================================
# 3. CORPORATE RECRUITER DOMAIN MISMATCH
# ============================================================================


@patch("agent.nodes.gate3_verifier._fetch_rdap")
@patch("agent.nodes.gate3_verifier._fetch_website")
@patch("socket.getaddrinfo")
def test_recruiter_company_mismatch(
    mock_dns,
    mock_website,
    mock_rdap,
):

    mock_dns.return_value = [
        (
            socket.AF_INET,
            socket.SOCK_STREAM,
            6,
            "",
            ("1.2.3.4", 443),
        )
    ]

    mock_website.return_value = website_result(
        "someotherdomain.com",
        reachable=True,
        title="Some Other Company",
        text_sample="Some Other Company careers",
    )

    mock_rdap.return_value = rdap_result(
        "someotherdomain.com"
    )

    inp = create_input(
        company_names=["Wipro"],
        email_addresses=["hr@someotherdomain.com"],
    )

    result = verify_company_recruiter_domain(inp)

    assert (
        result.recruiter_verification.status
        == VerificationStatus.SUSPICIOUS
    )

    assert (
        result.company_verification.status
        == VerificationStatus.SUSPICIOUS
    )


# ============================================================================
# 4. MISSING COMPANY
# ============================================================================


def test_missing_company():

    inp = create_input(
        email_addresses=["hr@unknown.com"]
    )

    result = verify_company_recruiter_domain(inp)

    assert (
        result.company_verification.status
        == VerificationStatus.UNKNOWN
    )


# ============================================================================
# 5. MISSING RECRUITER EMAIL
# ============================================================================


def test_missing_recruiter_email():

    inp = create_input(
        company_names=["HCL"]
    )

    result = verify_company_recruiter_domain(inp)

    assert (
        result.recruiter_verification.status
        == VerificationStatus.UNKNOWN
    )


# ============================================================================
# 6. MISSING DOMAIN
# ============================================================================


def test_missing_domain():

    inp = create_input(
        company_names=["Reliance"]
    )

    result = verify_company_recruiter_domain(inp)

    assert (
        result.domain_verification.status
        == VerificationStatus.UNKNOWN
    )


# ============================================================================
# 7. INVALID / NON-RESOLVING DOMAIN
# ============================================================================


@patch("agent.nodes.gate3_verifier._fetch_rdap")
@patch("agent.nodes.gate3_verifier._fetch_website")
@patch("socket.getaddrinfo")
def test_invalid_domain(
    mock_dns,
    mock_website,
    mock_rdap,
):

    mock_dns.side_effect = socket.gaierror(
        "Name or service not known"
    )

    mock_website.return_value = website_result(
        "thisdomaindoesnotexist.in",
        reachable=False,
        status_code=None,
        error="ConnectError",
    )

    mock_rdap.return_value = rdap_result(
        "thisdomaindoesnotexist.in",
        available=False,
        error="DOMAIN_NOT_FOUND",
    )

    inp = create_input(
        company_names=["FakeCorp"],
        urls=["http://thisdomaindoesnotexist.in"],
    )

    result = verify_company_recruiter_domain(inp)

    assert (
        result.domain_verification.status
        == VerificationStatus.SUSPICIOUS
    )


# ============================================================================
# 8. WEBSITE UNAVAILABLE BUT DOMAIN EXISTS
# ============================================================================


@patch("agent.nodes.gate3_verifier._fetch_rdap")
@patch("agent.nodes.gate3_verifier._fetch_website")
@patch("socket.getaddrinfo")
def test_website_unavailable(
    mock_dns,
    mock_website,
    mock_rdap,
):

    # DNS works
    mock_dns.return_value = [
        (
            socket.AF_INET,
            socket.SOCK_STREAM,
            6,
            "",
            ("1.2.3.4", 443),
        )
    ]

    # Website itself unavailable
    mock_website.return_value = website_result(
        "brokenwebsite.com",
        reachable=False,
        status_code=500,
        error=None,
    )

    # Domain registration exists
    mock_rdap.return_value = rdap_result(
        "brokenwebsite.com"
    )

    inp = create_input(
        urls=["https://brokenwebsite.com"]
    )

    result = verify_company_recruiter_domain(inp)

    # New Gate 3 correctly avoids calling an existing domain
    # fraudulent just because its website is temporarily unavailable.
    assert (
        result.domain_verification.status
        == VerificationStatus.UNKNOWN
    )


# ============================================================================
# 9. COMPANY / DOMAIN MISMATCH
# ============================================================================


@patch("agent.nodes.gate3_verifier._fetch_rdap")
@patch("agent.nodes.gate3_verifier._fetch_website")
@patch("socket.getaddrinfo")
def test_company_domain_mismatch(
    mock_dns,
    mock_website,
    mock_rdap,
):

    mock_dns.return_value = [
        (
            socket.AF_INET,
            socket.SOCK_STREAM,
            6,
            "",
            ("1.2.3.4", 443),
        )
    ]

    mock_website.return_value = website_result(
        "phishingsite.com",
        reachable=True,
        title="Welcome",
        text_sample="Online services",
    )

    mock_rdap.return_value = rdap_result(
        "phishingsite.com"
    )

    inp = create_input(
        company_names=["Tech Mahindra"],
        urls=["https://phishingsite.com"],
    )

    result = verify_company_recruiter_domain(inp)

    assert (
        result.company_verification.status
        == VerificationStatus.SUSPICIOUS
    )


# ============================================================================
# 10. MULTIPLE EMAILS
# ============================================================================


@patch("agent.nodes.gate3_verifier._fetch_rdap")
@patch("agent.nodes.gate3_verifier._fetch_website")
@patch("socket.getaddrinfo")
def test_multiple_verification_findings(
    mock_dns,
    mock_website,
    mock_rdap,
):

    mock_dns.return_value = [
        (
            socket.AF_INET,
            socket.SOCK_STREAM,
            6,
            "",
            ("1.2.3.4", 443),
        )
    ]

    mock_website.return_value = website_result(
        "cognizant.com",
        reachable=True,
        title="Cognizant Careers",
        text_sample="Cognizant careers jobs",
    )

    mock_rdap.return_value = rdap_result(
        "cognizant.com"
    )

    inp = create_input(
        company_names=["Cognizant"],
        email_addresses=[
            "hr@cognizant.com",
            "cognizant@yahoo.com",
        ],
    )

    result = verify_company_recruiter_domain(inp)

    assert (
        result.company_verification.status
        == VerificationStatus.VERIFIED
    )

    # Corporate email provides positive evidence.
    assert (
        result.recruiter_verification.metadata[
            "corporate_email_used"
        ]
        is True
    )

    # Generic provider was also detected.
    assert (
        result.recruiter_verification.metadata[
            "generic_provider_used"
        ]
        is True
    )

    # Because a valid corporate email exists and matches,
    # recruiter verification remains VERIFIED.
    assert (
        result.recruiter_verification.status
        == VerificationStatus.VERIFIED
    )


# ============================================================================
# 11. COMPLETELY UNKNOWN INPUT
# ============================================================================


def test_completely_unknown():

    inp = create_input()

    result = verify_company_recruiter_domain(inp)

    assert (
        result.company_verification.status
        == VerificationStatus.UNKNOWN
    )

    assert (
        result.recruiter_verification.status
        == VerificationStatus.UNKNOWN
    )

    assert (
        result.domain_verification.status
        == VerificationStatus.UNKNOWN
    )


# ============================================================================
# 12. NORMAL LEGITIMATE INDIAN COMPANY
# ============================================================================


@patch("agent.nodes.gate3_verifier._fetch_rdap")
@patch("agent.nodes.gate3_verifier._fetch_website")
@patch("socket.getaddrinfo")
def test_normal_legitimate_indian_company(
    mock_dns,
    mock_website,
    mock_rdap,
):

    mock_dns.return_value = [
        (
            socket.AF_INET,
            socket.SOCK_STREAM,
            6,
            "",
            ("1.2.3.4", 443),
        )
    ]

    mock_website.return_value = website_result(
        "zomato.com",
        reachable=True,
        status_code=200,
        title="Zomato Careers",
        text_sample="Zomato careers jobs opportunities",
    )

    mock_rdap.return_value = rdap_result(
        "zomato.com"
    )

    inp = create_input(
        company_names=["Zomato Private Limited"],
        email_addresses=["careers@zomato.com"],
        urls=["https://zomato.com/careers"],
    )

    result = verify_company_recruiter_domain(inp)

    assert (
        result.company_verification.status
        == VerificationStatus.VERIFIED
    )

    assert (
        result.recruiter_verification.status
        == VerificationStatus.VERIFIED
    )

    assert (
        result.domain_verification.status
        == VerificationStatus.VERIFIED
    )


# ============================================================================
# 13. COMPANY IMPERSONATION WITH GENERIC EMAIL
# ============================================================================


def test_suspicious_company_impersonation():

    inp = create_input(
        company_names=["Flipkart Limited"],
        email_addresses=[
            "flipkart.hr.department@outlook.com"
        ],
    )

    result = verify_company_recruiter_domain(inp)

    # Generic provider alone is not enough for a fraud verdict.
    assert (
        result.recruiter_verification.status
        == VerificationStatus.UNKNOWN
    )

    assert (
        result.recruiter_verification.metadata[
            "generic_provider_used"
        ]
        is True
    )


# ============================================================================
# 14. WEBSITE CONTENT SUPPORTS COMPANY IDENTITY
# ============================================================================


@patch("agent.nodes.gate3_verifier._fetch_rdap")
@patch("agent.nodes.gate3_verifier._fetch_website")
@patch("socket.getaddrinfo")
def test_website_identity_evidence(
    mock_dns,
    mock_website,
    mock_rdap,
):

    mock_dns.return_value = [
        (
            socket.AF_INET,
            socket.SOCK_STREAM,
            6,
            "",
            ("1.2.3.4", 443),
        )
    ]

    mock_website.return_value = website_result(
        "infosys.com",
        reachable=True,
        title="Infosys Limited",
        text_sample=(
            "Infosys Limited is a global technology "
            "services and consulting company."
        ),
    )

    mock_rdap.return_value = rdap_result(
        "infosys.com"
    )

    inp = create_input(
        company_names=["Infosys Limited"],
        urls=["https://infosys.com"],
    )

    result = verify_company_recruiter_domain(inp)

    checks = (
        result.company_verification
        .metadata["website_identity_checks"]
    )

    assert checks["infosys.com"]["identity_match"] is True


# ============================================================================
# 15. RDAP EVIDENCE IS PRESERVED
# ============================================================================


@patch("agent.nodes.gate3_verifier._fetch_rdap")
@patch("agent.nodes.gate3_verifier._fetch_website")
@patch("socket.getaddrinfo")
def test_rdap_evidence_is_preserved(
    mock_dns,
    mock_website,
    mock_rdap,
):

    mock_dns.return_value = [
        (
            socket.AF_INET,
            socket.SOCK_STREAM,
            6,
            "",
            ("1.2.3.4", 443),
        )
    ]

    mock_website.return_value = website_result(
        "example.com",
        reachable=True,
        title="Example",
        text_sample="Example website",
    )

    mock_rdap.return_value = rdap_result(
        "example.com",
        registration_date="2020-01-01T00:00:00Z",
        domain_age_days=2400,
    )

    inp = create_input(
        urls=["https://example.com"]
    )

    result = verify_company_recruiter_domain(inp)

    domain_checks = (
        result.domain_verification
        .metadata["domain_checks"]
    )

    rdap = domain_checks["example.com"]["rdap"]

    assert rdap["available"] is True
    assert rdap["registration_date"] == (
        "2020-01-01T00:00:00Z"
    )
    assert rdap["domain_age_days"] == 2400


# ============================================================================
# 16. REDIRECT EVIDENCE
# ============================================================================


@patch("agent.nodes.gate3_verifier._fetch_rdap")
@patch("agent.nodes.gate3_verifier._fetch_website")
@patch("socket.getaddrinfo")
def test_redirect_evidence(
    mock_dns,
    mock_website,
    mock_rdap,
):

    mock_dns.return_value = [
        (
            socket.AF_INET,
            socket.SOCK_STREAM,
            6,
            "",
            ("1.2.3.4", 443),
        )
    ]

    mock_website.return_value = website_result(
        "company.com",
        reachable=True,
        title="Company Careers",
        text_sample="Company careers",
        redirected=True,
        final_url="https://www.company.com/",
    )

    mock_rdap.return_value = rdap_result(
        "company.com"
    )

    inp = create_input(
        urls=["https://company.com"]
    )

    result = verify_company_recruiter_domain(inp)

    evidence = result.domain_verification.evidence

    assert any(
        "redirects to" in item
        for item in evidence
    )


# ============================================================================
# 17. GENERIC EMAIL PROVIDER IS NOT INVESTIGATED AS WEBSITE
# ============================================================================


def test_generic_email_domain_only():

    inp = create_input(
        email_addresses=["recruiter@gmail.com"]
    )

    result = verify_company_recruiter_domain(inp)

    assert (
        result.domain_verification.status
        == VerificationStatus.UNKNOWN
    )

    assert (
        result.recruiter_verification.status
        == VerificationStatus.UNKNOWN
    )


# ============================================================================
# 18. NO COMPANY BUT VALID CUSTOM EMAIL
# ============================================================================


@patch("agent.nodes.gate3_verifier._fetch_rdap")
@patch("agent.nodes.gate3_verifier._fetch_website")
@patch("socket.getaddrinfo")
def test_custom_email_without_company(
    mock_dns,
    mock_website,
    mock_rdap,
):

    mock_dns.return_value = [
        (
            socket.AF_INET,
            socket.SOCK_STREAM,
            6,
            "",
            ("1.2.3.4", 443),
        )
    ]

    mock_website.return_value = website_result(
        "unknowncompany.com",
        reachable=True,
        title="Unknown Company",
        text_sample="Careers",
    )

    mock_rdap.return_value = rdap_result(
        "unknowncompany.com"
    )

    inp = create_input(
        email_addresses=[
            "hr@unknowncompany.com"
        ]
    )

    result = verify_company_recruiter_domain(inp)

    # Company cannot be verified without a claimed company.
    assert (
        result.company_verification.status
        == VerificationStatus.UNKNOWN
    )

    # Recruiter cannot be matched against a company.
    assert (
        result.recruiter_verification.status
        == VerificationStatus.UNKNOWN
    )

    # Domain itself can still be technically investigated.
    assert (
        result.domain_verification.status
        == VerificationStatus.VERIFIED
    )