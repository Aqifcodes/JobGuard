"""Local tests for Gate 1: scam-signal / red-flag extraction.

Run directly:  py tests/test_flag_extractor.py
Or with pytest: py -m pytest tests/test_flag_extractor.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure the project root is on sys.path so imports work when run directly.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.nodes.gate1_flag_extractor import (
    Severity,
    extract_signals_from_text,
)

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _signal_types(result) -> set[str]:
    return {s.signal_type for s in result.signals}


def _get(result, signal_type):
    for s in result.signals:
        if s.signal_type == signal_type:
            return s
    return None


# ---------------------------------------------------------------------------
# 1. Explicit ₹ payment request
# ---------------------------------------------------------------------------


def test_explicit_rupee_payment_request() -> None:
    result = extract_signals_from_text("Pay ₹2500 registration fee.")
    sig = _get(result, "PAYMENT_REQUEST")
    assert sig is not None
    assert sig.severity is Severity.HIGH
    assert sig.confidence > 0.9
    assert "₹2500" in sig.matched_text
    assert sig.metadata.get("matched_phrase") == "registration fee"


# ---------------------------------------------------------------------------
# 2. Registration fee request
# ---------------------------------------------------------------------------


def test_registration_fee_request() -> None:
    result = extract_signals_from_text(
        "A registration fee of ₹500 is required to process your application."
    )
    sig = _get(result, "PAYMENT_REQUEST")
    assert sig is not None
    assert sig.severity is Severity.HIGH


# ---------------------------------------------------------------------------
# 3. UPI payment request
# ---------------------------------------------------------------------------


def test_upi_payment_request() -> None:
    result = extract_signals_from_text("Pay through UPI before your interview.")
    sig = _get(result, "UPI_PAYMENT_REQUEST")
    assert sig is not None
    assert sig.severity is Severity.HIGH


# ---------------------------------------------------------------------------
# 4. UPI PIN request
# ---------------------------------------------------------------------------


def test_upi_pin_request() -> None:
    result = extract_signals_from_text("Send your UPI PIN to complete verification.")
    sig = _get(result, "UPI_PIN_REQUEST")
    assert sig is not None
    assert sig.severity is Severity.HIGH
    # UPI PIN request should NOT also be flagged as a generic payment request.
    assert _get(result, "PAYMENT_REQUEST") is None


# ---------------------------------------------------------------------------
# 5. OTP request
# ---------------------------------------------------------------------------


def test_otp_request() -> None:
    result = extract_signals_from_text("Send your OTP to complete verification.")
    sig = _get(result, "OTP_REQUEST")
    assert sig is not None
    assert sig.severity is Severity.HIGH


# ---------------------------------------------------------------------------
# 6. Aadhaar request
# ---------------------------------------------------------------------------


def test_aadhaar_request() -> None:
    result = extract_signals_from_text("Please share your Aadhaar number.")
    sig = _get(result, "AADHAAR_REQUEST")
    assert sig is not None
    assert sig.severity is Severity.MEDIUM


# ---------------------------------------------------------------------------
# 7. PAN request
# ---------------------------------------------------------------------------


def test_pan_request() -> None:
    result = extract_signals_from_text("Provide your PAN card details.")
    sig = _get(result, "PAN_REQUEST")
    assert sig is not None
    assert sig.severity is Severity.MEDIUM


# ---------------------------------------------------------------------------
# 8. Bank details request
# ---------------------------------------------------------------------------


def test_bank_details_request() -> None:
    result = extract_signals_from_text("Share your bank account details.")
    sig = _get(result, "BANK_DETAILS_REQUEST")
    assert sig is not None
    assert sig.severity is Severity.MEDIUM


# ---------------------------------------------------------------------------
# 9. Generic Gmail recruiter email
# ---------------------------------------------------------------------------


def test_gmail_recruiter_email() -> None:
    result = extract_signals_from_text("Contact hrcompany@gmail.com for the job.")
    sig = _get(result, "PERSONAL_EMAIL_FOR_RECRUITMENT")
    assert sig is not None
    assert sig.severity is Severity.LOW
    assert "hrcompany@gmail.com" in sig.matched_text


# ---------------------------------------------------------------------------
# 10. Company-domain recruiter email
# ---------------------------------------------------------------------------


def test_company_domain_email() -> None:
    result = extract_signals_from_text("Contact careers@acmetech.com for the job.")
    assert _get(result, "PERSONAL_EMAIL_FOR_RECRUITMENT") is None


# ---------------------------------------------------------------------------
# 11. Urgency language
# ---------------------------------------------------------------------------


def test_urgency_language() -> None:
    result = extract_signals_from_text("Act immediately, limited seats available.")
    sig = _get(result, "URGENCY_PRESSURE")
    assert sig is not None
    assert sig.severity is Severity.MEDIUM
    assert "act immediately" in sig.metadata.get("matched_phrase", "").lower()


# ---------------------------------------------------------------------------
# 12. Guaranteed job claim
# ---------------------------------------------------------------------------


def test_guaranteed_job_claim() -> None:
    result = extract_signals_from_text("100% job guarantee, no experience needed.")
    sig = _get(result, "GUARANTEED_JOB_CLAIM")
    assert sig is not None
    assert sig.severity is Severity.MEDIUM


# ---------------------------------------------------------------------------
# 13. "Selected without interview"
# ---------------------------------------------------------------------------


def test_selected_without_interview() -> None:
    result = extract_signals_from_text("You will be selected without interview.")
    sig = _get(result, "SELECTED_WITHOUT_INTERVIEW")
    assert sig is not None
    assert sig.severity is Severity.MEDIUM


# ---------------------------------------------------------------------------
# 14. WhatsApp-only recruitment
# ---------------------------------------------------------------------------


def test_whatsapp_only_recruitment() -> None:
    result = extract_signals_from_text("Interview will be conducted on WhatsApp only.")
    sig = _get(result, "WHATSAPP_RECRUITMENT")
    assert sig is not None
    assert sig.severity is Severity.MEDIUM


# ---------------------------------------------------------------------------
# 15. Telegram-only recruitment
# ---------------------------------------------------------------------------


def test_telegram_only_recruitment() -> None:
    result = extract_signals_from_text("Interview will be conducted on Telegram only.")
    sig = _get(result, "TELEGRAM_RECRUITMENT")
    assert sig is not None
    assert sig.severity is Severity.MEDIUM


# ---------------------------------------------------------------------------
# 16. Unrealistic earning claim
# ---------------------------------------------------------------------------


def test_unrealistic_earning_claim() -> None:
    result = extract_signals_from_text("Earn ₹50,000 per week from home.")
    sig = _get(result, "SUSPICIOUS_INCOME_CLAIM")
    assert sig is not None
    assert sig.severity is Severity.MEDIUM


# ---------------------------------------------------------------------------
# 17. Legitimate "no application fee" statement
# ---------------------------------------------------------------------------


def test_no_application_fee_not_flagged() -> None:
    result = extract_signals_from_text("No application fee is required for this job.")
    assert _get(result, "PAYMENT_REQUEST") is None


# ---------------------------------------------------------------------------
# 18. Legitimate "never share OTP" statement
# ---------------------------------------------------------------------------


def test_never_share_otp_not_flagged() -> None:
    result = extract_signals_from_text("Never share your OTP with anyone.")
    assert _get(result, "OTP_REQUEST") is None


# ---------------------------------------------------------------------------
# 19. Normal salary statement
# ---------------------------------------------------------------------------


def test_normal_salary_not_flagged() -> None:
    result = extract_signals_from_text("Our salary is ₹40,000 per month.")
    assert _get(result, "PAYMENT_REQUEST") is None
    assert _get(result, "SUSPICIOUS_INCOME_CLAIM") is None


# ---------------------------------------------------------------------------
# 20. Normal CV request
# ---------------------------------------------------------------------------


def test_normal_cv_request_not_flagged() -> None:
    result = extract_signals_from_text("Please send your CV to apply.")
    assert result.total_signals == 0


# ---------------------------------------------------------------------------
# 21. Text containing multiple different signals
# ---------------------------------------------------------------------------


def test_multiple_different_signals() -> None:
    text = (
        "Pay ₹2500 registration fee. "
        "Send your OTP to complete verification. "
        "Contact hr@gmail.com. "
        "Act immediately, limited seats."
    )
    result = extract_signals_from_text(text)
    types = _signal_types(result)
    assert "PAYMENT_REQUEST" in types
    assert "OTP_REQUEST" in types
    assert "PERSONAL_EMAIL_FOR_RECRUITMENT" in types
    assert "URGENCY_PRESSURE" in types
    assert result.total_signals >= 4


# ---------------------------------------------------------------------------
# 22. Repeated identical warning (deduplication)
# ---------------------------------------------------------------------------


def test_repeated_identical_warning_deduplicated() -> None:
    text = "Pay ₹2500 registration fee. Pay ₹2500 registration fee."
    result = extract_signals_from_text(text)
    sig = _get(result, "PAYMENT_REQUEST")
    assert sig is not None
    # Only one PAYMENT_REQUEST signal, but it records both occurrences.
    assert result.total_signals == 1
    assert sig.metadata.get("match_count") == 2


# ---------------------------------------------------------------------------
# 23. Empty input
# ---------------------------------------------------------------------------


def test_empty_input() -> None:
    result = extract_signals_from_text("")
    assert result.total_signals == 0
    assert result.extraction_warnings


# ---------------------------------------------------------------------------
# 24. Input with no suspicious signals
# ---------------------------------------------------------------------------


def test_no_suspicious_signals() -> None:
    text = (
        "We are hiring a software engineer. "
        "Salary is ₹40,000 per month. "
        "Applications close on Friday."
    )
    result = extract_signals_from_text(text)
    assert result.total_signals == 0


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def _run_all() -> None:
    tests = [
        test_explicit_rupee_payment_request,
        test_registration_fee_request,
        test_upi_payment_request,
        test_upi_pin_request,
        test_otp_request,
        test_aadhaar_request,
        test_pan_request,
        test_bank_details_request,
        test_gmail_recruiter_email,
        test_company_domain_email,
        test_urgency_language,
        test_guaranteed_job_claim,
        test_selected_without_interview,
        test_whatsapp_only_recruitment,
        test_telegram_only_recruitment,
        test_unrealistic_earning_claim,
        test_no_application_fee_not_flagged,
        test_never_share_otp_not_flagged,
        test_normal_salary_not_flagged,
        test_normal_cv_request_not_flagged,
        test_multiple_different_signals,
        test_repeated_identical_warning_deduplicated,
        test_empty_input,
        test_no_suspicious_signals,
    ]
    passed = 0
    failed = 0
    for test_fn in tests:
        try:
            test_fn()
            print(f"PASS: {test_fn.__name__}")
            passed += 1
        except AssertionError as exc:
            print(f"FAIL: {test_fn.__name__}: {exc}")
            failed += 1
        except Exception as exc:  # noqa: BLE001
            print(f"ERROR: {test_fn.__name__}: {exc}")
            failed += 1

    print(f"\n{passed} passed, {failed} failed")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    _run_all()