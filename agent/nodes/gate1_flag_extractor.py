"""Gate 1: Hard scam-signal / red-flag extraction.

This module is the second stage of the multi-stage fraud investigation
pipeline. It consumes a standardized ``InvestigationInput`` produced by the
input-processing layer and extracts *observable* scam-related signals as
structured evidence.

ARCHITECTURE RULES
------------------
* This is GATE 1 ONLY. It does NOT:
    - calculate a scam probability or final verdict
    - decide whether a posting is legitimate
    - verify companies, domains, or recruiters
    - call an LLM, or use RAG / LangGraph
* Everything here is deterministic (regex / keyword / domain rules) so the
  layer stays predictable, testable, fast, cheap, and reproducible.
* ``severity`` and ``confidence`` are separate concepts:
    - severity  : how serious the signal itself is if it is truly present
    - confidence: how confident we are that the text actually contains it
  Neither is a "probability this job is a scam".
* Every signal preserves the exact text (``matched_text``) that caused it so
  the final system can be explainable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, Pattern

from .input_processor import InvestigationInput

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


class Severity(str, Enum):
    """How serious a signal is *if* it is genuinely present.

    Confidence is tracked separately from severity.
    """

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


@dataclass
class RiskSignal:
    """A single observable, scam-related signal extracted from an input.

    This is EVIDENCE, not a verdict. Later stages decide how much each
    signal matters.
    """

    signal_type: str
    title: str
    description: str
    evidence: str
    severity: Severity
    confidence: float
    source: str
    matched_text: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dict representation."""
        return {
            "signal_type": self.signal_type,
            "title": self.title,
            "description": self.description,
            "evidence": self.evidence,
            "severity": self.severity.value,
            "confidence": self.confidence,
            "source": self.source,
            "matched_text": self.matched_text,
            "metadata": dict(self.metadata),
        }


@dataclass
class SignalExtractionResult:
    """Structured output of ``extract_signals``.

    Deliberately contains NO final risk score or verdict.
    """

    signals: list[RiskSignal] = field(default_factory=list)
    extraction_warnings: list[str] = field(default_factory=list)

    @property
    def total_signals(self) -> int:
        return len(self.signals)

    @property
    def high_severity_count(self) -> int:
        return sum(1 for s in self.signals if s.severity is Severity.HIGH)

    @property
    def medium_severity_count(self) -> int:
        return sum(1 for s in self.signals if s.severity is Severity.MEDIUM)

    @property
    def low_severity_count(self) -> int:
        return sum(1 for s in self.signals if s.severity is Severity.LOW)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dict representation."""
        return {
            "signals": [s.to_dict() for s in self.signals],
            "total_signals": self.total_signals,
            "high_severity_count": self.high_severity_count,
            "medium_severity_count": self.medium_severity_count,
            "low_severity_count": self.low_severity_count,
            "extraction_warnings": list(self.extraction_warnings),
        }


# ---------------------------------------------------------------------------
# Static signal descriptions (title / description / evidence)
# ---------------------------------------------------------------------------

_SIGNAL_DESCRIPTIONS: dict[str, dict[str, str]] = {
    "PAYMENT_REQUEST": {
        "title": "Payment requested during recruitment",
        "description": (
            "The posting or recruiter asks the candidate to pay money, submit "
            "a fee, or make a deposit as part of the recruitment or onboarding "
            "process."
        ),
        "evidence": (
            "Explicit wording indicates the candidate is expected to pay "
            "money, a fee, or a deposit."
        ),
    },
    "UPI_PAYMENT_REQUEST": {
        "title": "UPI payment requested",
        "description": (
            "The posting asks the candidate to pay through UPI (an instant "
            "bank-to-bank payment system), often before or during recruitment."
        ),
        "evidence": "The text requests a payment via UPI.",
    },
    "PERSONAL_EMAIL_FOR_RECRUITMENT": {
        "title": "Personal email used for recruitment",
        "description": (
            "A free/personal email provider is used for recruitment contact "
            "instead of a corporate domain. Common among scammers, but also "
            "used by legitimate small recruiters - contextual evidence only."
        ),
        "evidence": (
            "An email address on a consumer mail provider was extracted from "
            "the contact details."
        ),
    },
    "URGENCY_PRESSURE": {
        "title": "Urgency or pressure tactics",
        "description": (
            "The posting applies time pressure or scarcity tactics to push the "
            "candidate to act quickly - a common manipulation technique."
        ),
        "evidence": "The text contains urgency or pressure wording.",
    },
    "GUARANTEED_JOB_CLAIM": {
        "title": "Guaranteed job or selection claim",
        "description": (
            "The posting claims a guaranteed job, placement, or selection, "
            "which is a common promise in employment scams."
        ),
        "evidence": "The text promises a guaranteed job, placement, or selection.",
    },
    "NO_INTERVIEW_REQUIRED": {
        "title": "No interview required claim",
        "description": (
            "The posting claims that no interview is required, bypassing "
            "standard screening. Contextual evidence only."
        ),
        "evidence": "The text states that no interview is required.",
    },
    "SELECTED_WITHOUT_INTERVIEW": {
        "title": "Selected without interview",
        "description": (
            "The posting claims the candidate will be selected without an "
            "interview. Contextual evidence only."
        ),
        "evidence": "The text states selection happens without an interview.",
    },
    "OTP_REQUEST": {
        "title": "OTP requested during recruitment",
        "description": (
            "The recruiter asks the candidate to provide a One-Time Password. "
            "This is a strong warning signal when requested during recruitment."
        ),
        "evidence": "The text requests an OTP from the candidate.",
    },
    "UPI_PIN_REQUEST": {
        "title": "UPI PIN requested during recruitment",
        "description": (
            "The recruiter asks the candidate to provide their UPI PIN. "
            "Sharing a UPI PIN can grant access to the candidate's bank account."
        ),
        "evidence": "The text requests a UPI PIN from the candidate.",
    },
    "CVV_REQUEST": {
        "title": "CVV requested during recruitment",
        "description": (
            "The recruiter asks for the CVV of a debit/credit card. This is a "
            "strong warning signal."
        ),
        "evidence": "The text requests a card CVV from the candidate.",
    },
    "BANKING_CREDENTIALS_REQUEST": {
        "title": "Banking or login credentials requested",
        "description": (
            "The recruiter asks for passwords, net-banking credentials, or "
            "login credentials. This is a strong warning signal."
        ),
        "evidence": (
            "The text requests passwords or banking/login credentials."
        ),
    },
    "AADHAAR_REQUEST": {
        "title": "Aadhaar details requested",
        "description": (
            "The recruiter asks for Aadhaar details. Aadhaar is sensitive "
            "personal information; such requests warrant scrutiny."
        ),
        "evidence": "The text requests Aadhaar details from the candidate.",
    },
    "PAN_REQUEST": {
        "title": "PAN details requested",
        "description": (
            "The recruiter asks for PAN details. PAN is sensitive personal "
            "information; such requests warrant scrutiny."
        ),
        "evidence": "The text requests PAN details from the candidate.",
    },
    "BANK_DETAILS_REQUEST": {
        "title": "Bank account details requested",
        "description": (
            "The recruiter asks for bank account details. This may be "
            "legitimate (e.g. salary account) but is also a common fraud hook."
        ),
        "evidence": "The text requests bank account details from the candidate.",
    },
    "CARD_DETAILS_REQUEST": {
        "title": "Debit/credit card details requested",
        "description": (
            "The recruiter asks for debit or credit card details. This is a "
            "strong warning signal in a recruitment context."
        ),
        "evidence": "The text requests card details from the candidate.",
    },
    "WHATSAPP_RECRUITMENT": {
        "title": "WhatsApp used for recruitment",
        "description": (
            "Recruitment contact happens over WhatsApp. Many legitimate "
            "recruiters use WhatsApp, so this is contextual evidence only."
        ),
        "evidence": "The text directs recruitment contact over WhatsApp.",
    },
    "TELEGRAM_RECRUITMENT": {
        "title": "Telegram used for recruitment",
        "description": (
            "Recruitment contact happens over Telegram. Contextual evidence only."
        ),
        "evidence": "The text directs recruitment contact over Telegram.",
    },
    "PLATFORM_TRANSFER_REQUEST": {
        "title": "Candidate asked to move to another platform",
        "description": (
            "The recruiter asks the candidate to move the conversation to "
            "another platform (WhatsApp, Telegram, etc.). This can bypass "
            "platform safeguards on legitimate job sites."
        ),
        "evidence": "The text asks the candidate to move the conversation to another platform.",
    },
    "JOB_OFFERED_IMMEDIATELY": {
        "title": "Job offered immediately / spot selection",
        "description": (
            "The posting offers the job immediately or promises on-the-spot "
            "selection. Contextual evidence only."
        ),
        "evidence": "The text claims an immediate job offer or spot selection.",
    },
    "SUSPICIOUS_INCOME_CLAIM": {
        "title": "Suspicious income / earning claim",
        "description": (
            "The posting makes claims such as high guaranteed earnings, "
            "earnings-per-week figures, or 'no skills required + guaranteed "
            "income' combinations. Whether the claim is unrealistic is decided "
            "later."
        ),
        "evidence": "The text contains an unusually framed income or earning claim.",
    },
    "CONTACT_RESTRICTION": {
        "title": "Candidate told not to contact the company",
        "description": (
            "The recruiter tells the candidate not to call or contact the "
            "company/office. Contextual evidence only."
        ),
        "evidence": "The text instructs the candidate not to contact the company.",
    },
}


# ---------------------------------------------------------------------------
# General text helpers
# ---------------------------------------------------------------------------

_SENTENCE_SPLIT_RE = re.compile(r"\n+|(?<=[.!?])\s+")

# Negation markers. Used for context-aware filtering of signals that have
# legitimate negative phrasing ("no application fee", "never share your OTP").
_NEGATION_TOKEN_RE = re.compile(
    r"(?i)\b(?:no|not|never|without|free|don'?t|do\s+not|does\s+not|did\s+not|"
    r"cannot|can'?t|won'?t|will\s+not|must\s+not|should\s+not|"
    r"no\s+need|not\s+required|not\s+applicable|not\s+needed|waived|exempt)\b"
)

_NEGATION_WINDOW_CHARS = 45


def _split_sentences(text: str) -> list[str]:
    """Split text into sentence-like units (newlines + sentence enders)."""
    return [part.strip() for part in _SENTENCE_SPLIT_RE.split(text) if part.strip()]


def _is_negated_sentence(sentence: str) -> bool:
    """True if any negation marker appears anywhere in the sentence."""
    return _NEGATION_TOKEN_RE.search(sentence) is not None


def _is_negated_window(sentence: str, match_start: int) -> bool:
    """True if a negation marker appears in the text before ``match_start``.

    Uses a limited window so a negation that belongs to a different clause
    (e.g. "no application fee, pay registration fee") does not suppress the
    signal.
    """
    start = max(0, match_start - _NEGATION_WINDOW_CHARS)
    before = sentence[start:match_start]
    return _NEGATION_TOKEN_RE.search(before) is not None


# ---------------------------------------------------------------------------
# Payment-related detection
# ---------------------------------------------------------------------------

_FEE_KEYWORD_PATTERNS: list[str] = [
    r"registration\s+fee",
    r"application\s+fee",
    r"interview\s+fee",
    r"security\s+deposit",
    r"security\s+charges",
    r"security\s+amount",
    r"training\s+fee",
    r"training\s+charges",
    r"processing\s+fee",
    r"processing\s+charges",
    r"document\s+verification\s+fee",
    r"verification\s+fee",
    r"joining\s+fee",
    r"joining\s+amount",
    r"onboarding\s+fee",
    r"refundable\s+deposit",
    r"advance\s+payment",
    r"advance\s+deposit",
    r"placement\s+fee",
    r"document\s+fee",
    r"document\s+charges",
    r"admin\s+fee",
    r"service\s+charges",
    r"service\s+fee",
    r"token\s+amount",
    r"booking\s+amount",
    r"caution\s+deposit",
    r"registration\s+charges",
    r"registration\s+amount",
    r"membership\s+fee",
    r"deposit\s+amount",
]
_FEE_KEYWORD_RE = re.compile(r"(?i)\b(?:%s)\b" % "|".join(_FEE_KEYWORD_PATTERNS))

_GENERIC_FEE_RE = re.compile(
    r"(?i)\b(?:fee|fees|deposit|charges?|any\s+payment|some\s+amount|money)\b"
)

_MONEY_RE = re.compile(
    r"(?i)(?:₹|rs\.?|inr|rupees?|rupee)\s*[\d,]+(?:\.\d+)?"
    r"|[\d,]+(?:\.\d+)?\s*(?:rupees?|rs\.?|inr)"
    r"|[\d,]+\s*(?:lakh|lpa|lacs?|crore|k|thousand)\b"
)

_PAYMENT_VERB_RE = re.compile(
    r"(?i)\b(?:pay|paying|paid|payment|payments|send|sent|transfer|remit|"
    r"deposit|give|submit|payable|make\s+(?:a|the)?\s*(?:payment|deposit|transfer)|"
    r"should\s+pay|must\s+pay|need\s+to\s+pay|have\s+to\s+pay)\b"
)

_PAYMENT_NOUN_RE = re.compile(
    r"(?i)\b(?:payment|deposit|fee|fees|charges?|amount|money|security\s+amount)\b"
)

_BEFORE_RECRUITMENT_EVENT_RE = re.compile(
    r"(?i)\b(?:before|prior\s+to)\s+(?:the\s+|your\s+)?"
    r"(?:joining|interview|onboarding|selection|placement|employment|"
    r"appointment|any\s+job|the\s+job|job\s+offer|offer\s+letter|training|"
    r"processing|verification|registration|confirmation)\b"
)

_PAYMENT_REQUIREMENT_RE = re.compile(
    r"(?i)\b(?:required|mandatory|compulsory|obligatory|"
    r"must\s+be\s+(?:paid|pay|made|submitted)|"
    r"need\s+to\s+be\s+(?:paid|made)|"
    r"to\s+(?:complete|confirm|process|register|verify|secure|activate|"
    r"unlock|release|finalize|proceed|continue))\b"
)

# Guards against "the company will pay you ₹40,000" (salary, not a request).
_PAY_TO_CANDIDATE_RE = re.compile(
    r"(?i)\b(?:will\s+)?(?:pay|paid)\s+(?:you|the\s+candidate|"
    r"selected\s+candidates?|employees?|staff|the\s+selected|the\s+employee)\b"
)

# Guards against "we pay a ₹40,000 salary" (salary, not a request).
_SALARY_CONTEXT_RE = re.compile(
    r"(?i)\b(?:salary|salaries|wages?|earnings?|stipend|remuneration|"
    r"compensation|ctc|take\s*[- ]home|basic\s+pay|pay\s+scale)\b"
)

_UPI_RE = re.compile(r"(?i)\bupi\b")
_UPI_PIN_RE = re.compile(r"(?i)\bupi\s*pin\b")
_UPI_ID_RE = re.compile(
    r"(?i)\b[\w.\-]+@(?:upi|ybl|okaxis|okicici|oksbi|okhdfc|paytm|apl|axl|ibl|"
    r"ptm|fbl|jio|airtel|freecharge|mobikwik|phonepe|gpay|bhim)\b"
)


def _sentence_payment_request(sentence: str) -> Optional[dict[str, Any]]:
    """Return payment-request details for a sentence, or None."""
    if _UPI_PIN_RE.search(sentence):
        # UPI PIN requests are handled by the stricter sensitive-info detector.
        return None

    fee_match = _FEE_KEYWORD_RE.search(sentence)
    money_match = _MONEY_RE.search(sentence)
    generic_fee_match = _GENERIC_FEE_RE.search(sentence)
    verb_match = _PAYMENT_VERB_RE.search(sentence)
    before_match = _BEFORE_RECRUITMENT_EVENT_RE.search(sentence)
    requirement_match = _PAYMENT_REQUIREMENT_RE.search(sentence)

    # Salary guards: the company paying the candidate is NOT a payment request.
    if verb_match and not fee_match and not requirement_match and not before_match:
        if _PAY_TO_CANDIDATE_RE.search(sentence) or _SALARY_CONTEXT_RE.search(sentence):
            return None

    # Determine the anchor for windowed negation (fee keyword first).
    anchor = fee_match.start() if fee_match else (
        money_match.start() if money_match else None
    )
    if anchor is not None and _is_negated_window(sentence, anchor):
        return None

    if verb_match and (fee_match or money_match or generic_fee_match):
        # "Pay ₹2500 registration fee", "Send ₹5000", "Pay a fee", ...
        return {
            "request_type": "fee",
            "fee_keyword": fee_match.group(0) if fee_match else None,
            "money": money_match.group(0) if money_match else None,
        }

    if fee_match and (requirement_match or before_match):
        # "Security deposit is required before joining", "Registration fee mandatory"
        return {
            "request_type": "fee",
            "fee_keyword": fee_match.group(0),
            "money": money_match.group(0) if money_match else None,
        }

    if _PAYMENT_NOUN_RE.search(sentence) and before_match:
        # "Payment before joining", "Any payment before the interview"
        return {
            "request_type": "before_event",
            "fee_keyword": None,
            "money": money_match.group(0) if money_match else None,
        }

    if verb_match and before_match:
        # "Pay before the interview", "Transfer money before joining"
        return {
            "request_type": "before_event",
            "fee_keyword": None,
            "money": money_match.group(0) if money_match else None,
        }

    return None


def _sentence_upi_payment_request(sentence: str) -> Optional[dict[str, Any]]:
    """Return UPI-payment details for a sentence, or None."""
    if _UPI_PIN_RE.search(sentence):
        return None  # handled by stricter UPI_PIN_REQUEST signal

    upi_id = _UPI_ID_RE.search(sentence)
    if upi_id:
        return {
            "upi_handle": upi_id.group(0),
            "request_type": "upi_handle",
            "money": (_MONEY_RE.search(sentence).group(0) if _MONEY_RE.search(sentence) else None),
        }

    if not _UPI_RE.search(sentence):
        return None

    has_payment_verb = _PAYMENT_VERB_RE.search(sentence) is not None
    has_payment_noun = _PAYMENT_NOUN_RE.search(sentence) is not None
    has_money = _MONEY_RE.search(sentence) is not None
    has_before = _BEFORE_RECRUITMENT_EVENT_RE.search(sentence) is not None
    has_requirement = _PAYMENT_REQUIREMENT_RE.search(sentence) is not None

    if not (has_payment_verb or has_payment_noun or has_money or has_before or has_requirement):
        return None

    return {
        "request_type": "upi",
        "upi_handle": None,
        "money": (_MONEY_RE.search(sentence).group(0) if _MONEY_RE.search(sentence) else None),
    }


# ---------------------------------------------------------------------------
# Sensitive information requests
# ---------------------------------------------------------------------------

_REQUEST_VERB_RE = re.compile(
    r"(?i)\b(?:send|share|provide|give|submit|upload|enter|furnish|disclose|"
    r"confirm|verify|need|need\s+your|required|requires|please\s+share|"
    r"kindly\s+share|tell|inform|email|whatsapp|forward|paste|type|fill|update|"
    r"add|attach|text|dm)\b"
)

# (signal_type, regex) - the request-verb + negation check decides firing.
_SENSITIVE_INFO_RULES: list[tuple[str, Pattern[str]]] = [
    ("OTP_REQUEST", re.compile(r"(?i)\botp\b")),
    ("UPI_PIN_REQUEST", re.compile(r"(?i)\bupi\s*pin\b")),
    ("CVV_REQUEST", re.compile(r"(?i)\bcvv\b")),
    (
        "BANKING_CREDENTIALS_REQUEST",
        re.compile(
            r"(?i)\b(?:net\s+banking|internet\s+banking|online\s+banking)\s+"
            r"(?:password|credentials?|login|user\s*id|id)"
            r"|banking\s+credentials?|login\s+credentials?|account\s+password|"
            r"bank\s+password|email\s+password|customer\s+id.*password\b"
        ),
    ),
    ("AADHAAR_REQUEST", re.compile(r"(?i)\baadha?ar\b")),
    (
        "PAN_REQUEST",
        re.compile(r"(?i)\b(?:pan\s+card|pan\s+number|permanent\s+account\s+number)\b"),
    ),
    (
        "BANK_DETAILS_REQUEST",
        re.compile(
            r"(?i)\b(?:bank\s+(?:account|details?|a\s*\/\s*c)|"
            r"account\s+(?:number|details?)|savings\s+account|current\s+account)\b"
        ),
    ),
    (
        "CARD_DETAILS_REQUEST",
        re.compile(r"(?i)\b(?:debit\s+card|credit\s+card|card\s+number|card\s+details?)\b"),
    ),
]

# Base confidence per sensitive signal type.
_SENSITIVE_BASE_CONFIDENCE: dict[str, float] = {
    "OTP_REQUEST": 0.98,
    "UPI_PIN_REQUEST": 0.99,
    "CVV_REQUEST": 0.99,
    "BANKING_CREDENTIALS_REQUEST": 0.95,
    "AADHAAR_REQUEST": 0.9,
    "PAN_REQUEST": 0.9,
    "BANK_DETAILS_REQUEST": 0.9,
    "CARD_DETAILS_REQUEST": 0.9,
}

# Severity per sensitive signal type. OTP / UPI PIN / CVV / banking
# credentials are strong warning signals when requested during recruitment.
_SENSITIVE_SEVERITY: dict[str, str] = {
    "OTP_REQUEST": "HIGH",
    "UPI_PIN_REQUEST": "HIGH",
    "CVV_REQUEST": "HIGH",
    "BANKING_CREDENTIALS_REQUEST": "HIGH",
    "AADHAAR_REQUEST": "MEDIUM",
    "PAN_REQUEST": "MEDIUM",
    "BANK_DETAILS_REQUEST": "MEDIUM",
    "CARD_DETAILS_REQUEST": "HIGH",
}


def _sentence_sensitive_requests(sentence: str) -> list[dict[str, Any]]:
    """Return sensitive-info request details for a sentence, or []."""
    if _is_negated_sentence(sentence):
        # "Never share your OTP." / "Please do not share your Aadhaar."
        return []

    verb_match = _REQUEST_VERB_RE.search(sentence)
    if not verb_match:
        return []

    results: list[dict[str, Any]] = []
    for signal_type, pattern in _SENSITIVE_INFO_RULES:
        m = pattern.search(sentence)
        if m:
            results.append(
                {
                    "signal_type": signal_type,
                    "info_keyword": m.group(0),
                    "request_verb": verb_match.group(0),
                    "confidence": _SENSITIVE_BASE_CONFIDENCE[signal_type],
                    "severity": _SENSITIVE_SEVERITY[signal_type],
                    "phrase": m.group(0),
                }
            )
    return results


# ---------------------------------------------------------------------------
# Urgency / pressure detection
# ---------------------------------------------------------------------------

# (regex, is_payment_urgency) - payment urgency elevates severity to HIGH.
_URGENCY_RULES: list[tuple[str, bool]] = [
    (r"\bact\s+(?:now|immediately|fast|quickly)\b", False),
    (r"\bpay\s+today\b", True),
    (r"\bimmediate\s+payment\b", True),
    (r"\burgent\s+payment\b", True),
    (r"\blimited\s+(?:seats?|slots?|vacancies?|positions?|openings?)\b", False),
    (r"\b(?:only|just)\s+\d+\s+(?:seats?|slots?|vacancies?|positions?)\s+left\b", False),
    (
        r"\boffer\s+expires?\s+(?:today|soon|tonight|now|"
        r"in\s+the\s+next\s+\d+\s*(?:hours?|days?))\b",
        False,
    ),
    (r"\b(?:offer|opportunity)\s+expires?\s+within\s+\d+\s*(?:hours?|days?)\b", False),
    (r"\brespond\s+(?:within|in)\s+(?:one\s+)?(?:hour|hours|day|days|24\s+hours?)\b", False),
    (r"\b(?:reply|respond|confirm)\s+within\s+the\s+next\s+\d+\s*(?:hours?|days?)\b", False),
    (r"\b(?:don'?t|do\s+not)\s+miss\s+this\s+opportunity\b", False),
    (r"\bfinal\s+warning\b", False),
    (r"\blast\s+(?:chance|call|warning)\b", False),
    (r"\blast\s+\d+\s+(?:seats?|slots?|vacancies?)\b", False),
    (r"\bhurry\s*(?:up)?\s*(?:today|now)?\b", False),
    (r"\bseats?\s+(?:are\s+)?filling\s+fast\b", False),
    (r"\bwithout\s+delay\b", False),
]

_URGENCY_RULES_COMPILED: list[tuple[Pattern[str], bool]] = [
    (re.compile(pat, re.IGNORECASE), is_pay) for pat, is_pay in _URGENCY_RULES
]

_NO_HURRY_RE = re.compile(r"(?i)\b(?:no\s+hurry|don'?t\s+hurry|not\s+in\s+a\s+hurry)\b")


def _sentence_urgency(sentence: str) -> Optional[dict[str, Any]]:
    """Return urgency phrase details for a sentence, or None."""
    for pattern, is_payment in _URGENCY_RULES_COMPILED:
        m = pattern.search(sentence)
        if m is None:
            continue
        phrase = m.group(0).strip().rstrip("!.")
        if re.search(r"(?i)\bhurry\b", phrase) and _NO_HURRY_RE.search(sentence):
            continue
        return {"phrase": phrase, "is_payment_urgency": is_payment}
    return None


# ---------------------------------------------------------------------------
# Guaranteed job / selection claims
# ---------------------------------------------------------------------------

_GUARANTEED_JOB_RE = re.compile(
    r"(?i)\b(?:"
    r"100%\s*(?:job|placement|selection|guarantee)"
    r"|(?:job|placement|selection|appointment|employment|offer\s+letter)\s+"
    r"(?:is\s+)?guaranteed"
    r"|guaranteed\s+(?:job|placement|selection|appointment|employment|offer\s+letter)"
    r"|guarantee\s+of\s+(?:job|placement|selection)"
    r"|(?:get|receive|secure|obtain)\s+(?:a\s+)?(?:job|placement)\s+guaranteed"
    r"|job\s+guaranteed\s+after\s+payment"
    r")\b"
)

_NO_INTERVIEW_RE = re.compile(
    r"(?i)\b(?:no|without|skip(?:ping)?|no\s+need\s+for)\s+"
    r"(?:any\s+|the\s+)?(?:interview|personal\s+interview|written\s+test|exam|test)"
    r"\b\s*(?:required|needed)?"
)

_SELECTED_WITHOUT_INTERVIEW_RE = re.compile(
    r"(?i)\b(?:"
    r"(?:selected|selection|choose|chosen|shortlisted|hired|appointed|placed)\s+"
    r"(?:without|skipping|having\s+no)\s+(?:an\s+|the\s+)?(?:interview|exam|test)"
    r"|direct\s+(?:selection|placement|appointment)"
    r")\b"
)


def _sentence_guaranteed_claims(sentence: str) -> list[dict[str, Any]]:
    """Return guaranteed-job related claim details for a sentence, or []."""
    results: list[dict[str, Any]] = []

    gm = _GUARANTEED_JOB_RE.search(sentence)
    if gm:
        severity = "HIGH" if re.search(r"(?i)\bpayment\b", sentence) else "MEDIUM"
        results.append(
            {
                "signal_type": "GUARANTEED_JOB_CLAIM",
                "phrase": gm.group(0),
                "severity": severity,
                "confidence": 0.92,
            }
        )

    nm = _NO_INTERVIEW_RE.search(sentence)
    if nm:
        results.append(
            {
                "signal_type": "NO_INTERVIEW_REQUIRED",
                "phrase": nm.group(0),
                "severity": "MEDIUM",
                "confidence": 0.9,
            }
        )

    sm = _SELECTED_WITHOUT_INTERVIEW_RE.search(sentence)
    if sm:
        results.append(
            {
                "signal_type": "SELECTED_WITHOUT_INTERVIEW",
                "phrase": sm.group(0),
                "severity": "MEDIUM",
                "confidence": 0.92,
            }
        )

    return results


# ---------------------------------------------------------------------------
# WhatsApp / Telegram / platform-transfer detection
# ---------------------------------------------------------------------------

_PLATFORM_RE = re.compile(r"(?i)\b(whatsapp|telegram)\b")
_INTERVIEW_ONLY_RE = re.compile(r"(?i)\b(?:only|exclusively)\b")
_INTERVIEW_CONTEXT_RE = re.compile(r"(?i)\b(?:interview|selection|joining|test|job)\b")
_PLATFORM_ACTION_RE = re.compile(
    r"(?i)\b(?:contact|call|message|chat|reach|add|join|connect|send|share|"
    r"apply|talk|discuss|dm|ping|text|reply|on|via|over|through|group|number|"
    r"only|exclusively|for|to)\b"
)

_PLATFORM_TRANSFER_RE = re.compile(
    r"(?i)\b(?:"
    r"(?:move|shift|switch|transfer)\s+(?:to|onto|on|over)\s+"
    r"(?:whatsapp|telegram|skype|zoom|google\s+chat|hangouts|signal|wechat|"
    r"facebook\s+messenger)"
    r"|(?:continue|carry\s+on|discuss|talk|chat|communicate|take\s+forward)\s+"
    r"(?:this\s+)?(?:conversation|discussion|further|details|process)?\s*"
    r"(?:on|via|over|through)\s+"
    r"(?:whatsapp|telegram|skype|zoom|google\s+chat|hangouts|signal|wechat)"
    r"|join\s+(?:our\s+|the\s+)?(?:whatsapp|telegram)\s+(?:group|channel)"
    r"|add\s+(?:me|us)\s+on\s+(?:whatsapp|telegram)"
    r"|contact\s+(?:me|us)\s+(?:on|via|at|through)\s+(?:whatsapp|telegram)\s+"
    r"(?:for\s+(?:the\s+)?(?:interview|selection)|only)"
    r")\b",
)


def _sentence_platform_signals(sentence: str) -> list[dict[str, Any]]:
    """Return WhatsApp/Telegram/platform-transfer details for a sentence, or []."""
    results: list[dict[str, Any]] = []

    transfer = _PLATFORM_TRANSFER_RE.search(sentence)
    if transfer:
        results.append(
            {
                "signal_type": "PLATFORM_TRANSFER_REQUEST",
                "phrase": transfer.group(0),
                "severity": "MEDIUM",
                "confidence": 0.9,
            }
        )

    pm = _PLATFORM_RE.search(sentence)
    if not pm:
        return results

    platform = pm.group(1).lower()
    signal_type = (
        "WHATSAPP_RECRUITMENT" if platform == "whatsapp" else "TELEGRAM_RECRUITMENT"
    )

    if not _PLATFORM_ACTION_RE.search(sentence):
        return results

    interview_only = bool(
        _INTERVIEW_CONTEXT_RE.search(sentence) and _INTERVIEW_ONLY_RE.search(sentence)
    )
    severity = "MEDIUM" if interview_only else "LOW"

    results.append(
        {
            "signal_type": signal_type,
            "phrase": pm.group(0),
            "severity": severity,
            "confidence": 0.9,
            "platform": platform,
            "interview_only": interview_only,
        }
    )
    return results


# ---------------------------------------------------------------------------
# Job-offered-immediately / selection shortcuts
# ---------------------------------------------------------------------------

_JOB_OFFERED_IMMEDIATELY_RE = re.compile(
    r"(?i)\b(?:"
    r"(?:job|employment|appointment|offer|offer\s+letter|appointment\s+letter)\s+"
    r"(?:offered|confirm|confirmed|granted|given)\s+"
    r"(?:immediately|instantly|right\s+away|on\s+the\s+spot|on\s+spot|today)"
    r"|(?:on[- ]the[- ]spot|instant|immediate|direct)\s+"
    r"(?:selection|appointment|placement|offer)"
    r"|selected\s+(?:immediately|instantly|right\s+away|today)"
    r")\b"
)


def _sentence_job_offered_immediately(sentence: str) -> Optional[dict[str, Any]]:
    m = _JOB_OFFERED_IMMEDIATELY_RE.search(sentence)
    if m:
        return {"phrase": m.group(0), "severity": "MEDIUM", "confidence": 0.85}
    return None


# ---------------------------------------------------------------------------
# Contact-restriction detection
# ---------------------------------------------------------------------------

_CONTACT_RESTRICTION_RE = re.compile(
    r"(?i)\b(?:don'?t|do\s+not|never|must\s+not|should\s+not|avoid)\s+"
    r"(?:to\s+)?(?:call|contact|visit|approach|reach\s+out\s+to)\s+"
    r"(?:the\s+|our\s+)?(?:company|office|head\s+office|corporate\s+office|"
    r"hr\s+department|hr\s+team)\b"
)


def _sentence_contact_restriction(sentence: str) -> Optional[dict[str, Any]]:
    m = _CONTACT_RESTRICTION_RE.search(sentence)
    if m:
        return {"phrase": m.group(0), "severity": "LOW", "confidence": 0.7}
    return None


# ---------------------------------------------------------------------------
# Suspicious income / earning claims
# ---------------------------------------------------------------------------

_INCOME_CLAIM_RE = re.compile(
    r"(?i)\b(?:earn|earning|earn\s+up\s+to|income|make|receive|get|payout|"
    r"take\s+home)\b"
    r".{0,50}?"
    r"(?:₹|rs\.?|inr|rupees?)\s*[\d,]+(?:\.\d+)?"
    r".{0,40}?"
    r"\b(?:per|every|each|weekly|daily|monthly)\s*(?:week|day|month)?\b"
)

_GUARANTEED_INCOME_RE = re.compile(
    r"(?i)\bguaranteed?\s+(?:income|earnings?|salary|payout|money)\b"
)

_WFH_RE = re.compile(r"(?i)\bwork\s+from\s+home\b")

_NO_SKILLS_RE = re.compile(
    r"(?i)\bno\s+(?:skills?|experience|qualifications?|degree|education|training)\s+"
    r"required\b"
)

_AMOUNT_FREQUENCY_RE = re.compile(
    r"(?i)(?:₹|rs\.?|inr|rupees?)\s*[\d,]+(?:\.\d+)?"
    r".{0,30}?"
    r"\b(?:per|every|each|weekly|daily|monthly)\s*(?:week|day|month)?\b"
)

_INCOME_VERB_RE = re.compile(
    r"(?i)\b(?:earn|earning|earn\s+up\s+to|income|make|receive|get|payout|"
    r"take\s+home)\b"
)


def _sentence_income_claim(sentence: str) -> Optional[dict[str, Any]]:
    """Return suspicious income-claim details for a sentence, or None."""
    if _INCOME_CLAIM_RE.search(sentence):
        return {
            "phrase": "frequent earning claim with an amount",
            "severity": "MEDIUM",
            "confidence": 0.85,
        }

    if _GUARANTEED_INCOME_RE.search(sentence):
        return {
            "phrase": "guaranteed income claim",
            "severity": "MEDIUM",
            "confidence": 0.9,
        }

    if _WFH_RE.search(sentence) and (
        _INCOME_VERB_RE.search(sentence)
        or _GUARANTEED_INCOME_RE.search(sentence)
        or _AMOUNT_FREQUENCY_RE.search(sentence)
    ):
        return {
            "phrase": "work-from-home with high earning claim",
            "severity": "MEDIUM",
            "confidence": 0.85,
        }

    if _NO_SKILLS_RE.search(sentence) and (
        _MONEY_RE.search(sentence)
        or _INCOME_VERB_RE.search(sentence)
        or _GUARANTEED_INCOME_RE.search(sentence)
    ):
        return {
            "phrase": "no skills required plus income/money claim",
            "severity": "MEDIUM",
            "confidence": 0.85,
        }

    return None


# ---------------------------------------------------------------------------
# Consumer / personal email providers
# ---------------------------------------------------------------------------

_CONSUMER_EMAIL_DOMAINS: set[str] = {
    "gmail.com",
    "googlemail.com",
    "yahoo.com",
    "yahoo.co.in",
    "yahoo.in",
    "outlook.com",
    "hotmail.com",
    "live.com",
    "msn.com",
    "rediffmail.com",
    "rediff.com",
    "ymail.com",
    "aol.com",
    "icloud.com",
    "me.com",
    "protonmail.com",
    "proton.me",
    "mail.com",
    "gmx.com",
    "gmx.net",
    "zoho.com",
    "fastmail.com",
    "yandex.com",
    "yandex.ru",
}


def _personal_email_signals(investigation_input: InvestigationInput) -> list[dict[str, Any]]:
    """Return personal-email signal details from extracted email addresses."""
    results: list[dict[str, Any]] = []
    for email in investigation_input.email_addresses:
        if "@" not in email:
            continue
        domain = email.rsplit("@", 1)[1].strip().lower()
        if domain in _CONSUMER_EMAIL_DOMAINS:
            results.append(
                {
                    "signal_type": "PERSONAL_EMAIL_FOR_RECRUITMENT",
                    "phrase": email,
                    "severity": "LOW",
                    "confidence": 0.98,
                    "domain": domain,
                }
            )
    return results


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


class _SignalDetector:
    """Runs all deterministic detectors over one ``InvestigationInput``."""

    def __init__(self, investigation_input: InvestigationInput) -> None:
        self.input = investigation_input
        self.text = investigation_input.extracted_text or ""
        self.raw_hits: list[dict[str, Any]] = []

    def run(self) -> SignalExtractionResult:
        if not self.text.strip():
            return SignalExtractionResult(
                extraction_warnings=[
                    "No text available to extract signals from; the input is empty."
                ]
            )

        warnings: list[str] = []
        if not self.input.email_addresses:
            warnings.append(
                "No email addresses extracted; personal-email checks were skipped."
            )

        # Pre-compute personal-email signals from the extracted entity list.
        for hit in _personal_email_signals(self.input):
            self._append_hit(hit, source="email_addresses")

        for sentence in _split_sentences(self.text):
            self._run_sentence(sentence)

        signals = self._build_signals()
        return SignalExtractionResult(signals=signals, extraction_warnings=warnings)

    def _run_sentence(self, sentence: str) -> None:
        self._run_payment(sentence)
        self._run_sensitive(sentence)
        self._run_urgency(sentence)
        self._run_guaranteed(sentence)
        self._run_platforms(sentence)
        self._run_immediate_offer(sentence)
        self._run_contact_restriction(sentence)
        self._run_income_claim(sentence)

    # -- sub-detectors ----------------------------------------------------

    def _run_payment(self, sentence: str) -> None:
        payment = _sentence_payment_request(sentence)
        if payment:
            self._append_hit(
                {
                    "signal_type": "PAYMENT_REQUEST",
                    "severity": "HIGH",
                    "confidence": 0.96,
                    **payment,
                    "phrase": (
                        payment.get("fee_keyword")
                        or payment.get("money")
                        or "payment request"
                    ),
                },
                sentence,
            )

        upi = _sentence_upi_payment_request(sentence)
        if upi:
            self._append_hit(
                {
                    "signal_type": "UPI_PAYMENT_REQUEST",
                    "severity": "HIGH",
                    "confidence": 0.97,
                    **upi,
                    "phrase": upi.get("upi_handle") or "UPI payment",
                },
                sentence,
            )

    def _run_sensitive(self, sentence: str) -> None:
        for hit in _sentence_sensitive_requests(sentence):
            self._append_hit(hit, sentence)

    def _run_urgency(self, sentence: str) -> None:
        urgency = _sentence_urgency(sentence)
        if urgency:
            self._append_hit(
                {
                    "signal_type": "URGENCY_PRESSURE",
                    "severity": "HIGH" if urgency.pop("is_payment_urgency", False) else "MEDIUM",
                    "confidence": 0.85,
                    **urgency,
                },
                sentence,
            )

    def _run_guaranteed(self, sentence: str) -> None:
        for hit in _sentence_guaranteed_claims(sentence):
            self._append_hit(hit, sentence)

    def _run_platforms(self, sentence: str) -> None:
        for hit in _sentence_platform_signals(sentence):
            self._append_hit(hit, sentence)

    def _run_immediate_offer(self, sentence: str) -> None:
        hit = _sentence_job_offered_immediately(sentence)
        if hit:
            self._append_hit(
                {"signal_type": "JOB_OFFERED_IMMEDIATELY", **hit}, sentence
            )

    def _run_contact_restriction(self, sentence: str) -> None:
        hit = _sentence_contact_restriction(sentence)
        if hit:
            self._append_hit(
                {"signal_type": "CONTACT_RESTRICTION", **hit}, sentence
            )

    def _run_income_claim(self, sentence: str) -> None:
        hit = _sentence_income_claim(sentence)
        if hit:
            self._append_hit(
                {"signal_type": "SUSPICIOUS_INCOME_CLAIM", **hit}, sentence
            )

    # -- helpers ----------------------------------------------------------

    def _append_hit(
        self,
        hit: dict[str, Any],
        source: str,
    ) -> None:
        self.raw_hits.append({**hit, "_source": source})

    def _build_signals(self) -> list[RiskSignal]:
        """Convert hits into deduplicated RiskSignal objects."""
        grouped: dict[str, list[dict[str, Any]]] = {}
        for hit in self.raw_hits:
            grouped.setdefault(hit["signal_type"], []).append(hit)

        result: list[RiskSignal] = []
        for signal_type, hits in grouped.items():
            meta = _SIGNAL_DESCRIPTIONS[signal_type]
            best = max(hits, key=_hit_strength)
            source = best["_source"]

            matched_text = self.text
            # For personal-email signals the source text is the email itself.
            if source == "email_addresses":
                matched_text = best["phrase"]

            metadata: dict[str, Any] = {}
            for key, value in best.items():
                if key not in ("signal_type", "severity", "confidence", "_source", "phrase"):
                    metadata[key] = value
            if best.get("phrase") is not None:
                metadata["matched_phrase"] = best["phrase"]

            other_matches = [
                h["phrase"]
                for h in hits
                if h.get("phrase") not in (None, best.get("phrase"))
            ]
            other_matches = list({m for m in other_matches if m})[:5]
            metadata["match_count"] = len(hits)
            if other_matches:
                metadata["additional_matches"] = other_matches

            result.append(
                RiskSignal(
                    signal_type=signal_type,
                    title=meta["title"],
                    description=meta["description"],
                    evidence=meta["evidence"],
                    severity=Severity(best["severity"]),
                    confidence=float(best["confidence"]),
                    source=source,
                    matched_text=matched_text,
                    metadata=metadata,
                )
            )

        # Preserve first-seen order of signal types.
        order: list[str] = []
        for hit in self.raw_hits:
            t = hit["signal_type"]
            if t not in order:
                order.append(t)
        by_type = {sig.signal_type: sig for sig in result}
        return [by_type[t] for t in order]


def _hit_strength(hit: dict[str, Any]) -> tuple[int, float, int]:
    """Dedup strength: severity rank, then confidence, then evidence length."""
    severity_rank = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}.get(
        hit.get("severity", "LOW"), 0
    )
    confidence = float(hit.get("confidence", 0.0))
    phrase_len = len(str(hit.get("phrase", "")))
    return (severity_rank, confidence, phrase_len)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def extract_signals(investigation_input: InvestigationInput) -> SignalExtractionResult:
    """Extract observable scam-related signals from a processed input.

    Args:
        investigation_input: The standardized input produced by the
            input-processing layer.

    Returns:
        A ``SignalExtractionResult`` containing structured evidence signals.
        This result deliberately contains no final risk score or verdict.
    """
    return _SignalDetector(investigation_input).run()


def extract_signals_from_text(text: str) -> SignalExtractionResult:
    """Convenience wrapper for plain-text inputs.

    Args:
        text: Plain text to analyze.

    Returns:
        A ``SignalExtractionResult``.
    """
    from ._extractors import extract_all
    from .input_processor import SourceType

    entities = extract_all(text)
    return extract_signals(
        InvestigationInput(
            source_type=SourceType.TEXT,
            raw_text=text,
            extracted_text=text,
            urls=entities["urls"],
            email_addresses=entities["email_addresses"],
            phone_numbers=entities["phone_numbers"],
            company_names=entities["company_names"],
            recruiter_names=entities["recruiter_names"],
            job_titles=entities["job_titles"],
            locations=entities["locations"],
            salary_mentions=entities["salary_mentions"],
        )
    )


__all__ = [
    "Severity",
    "RiskSignal",
    "SignalExtractionResult",
    "extract_signals",
    "extract_signals_from_text",
]