"""Gate 5: LLM Evidence Reasoning.

Gate 5 receives evidence from Gates 1-4 and produces:

* structured assessment
* confidence
* 4-5 reasoning points
* 4-5 recommendations
* supporting evidence
* contradicting evidence
* warnings

Gate 5 does NOT perform external verification and does NOT replace
the deterministic evidence produced by Gates 1-4.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any
from urllib import response

from google import genai
from google.genai import types

# ---------------------------------------------------------------------------
# Data Model
# ---------------------------------------------------------------------------


@dataclass
class LLMAnalysisResult:
    """Structured reasoning produced by Gate 5."""

    assessment: str
    confidence: float
    reasoning: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    supporting_evidence: list[str] = field(default_factory=list)
    contradicting_evidence: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    model_name: str = "gemini-2.5-flash"

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""
        return {
            "assessment": self.assessment,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "recommendations": self.recommendations,
            "supporting_evidence": self.supporting_evidence,
            "contradicting_evidence": self.contradicting_evidence,
            "warnings": self.warnings,
            "model_name": self.model_name,
        }


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_MODEL = "gemini-2.5-flash"

# Number of attempts for temporary Gemini server failures.
MAX_RETRIES = 3

# Initial delay before retrying.
RETRY_DELAY_SECONDS = 2

# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

SYSTEM_INSTRUCTION = """
You are the evidence-reasoning component of an Indian Job Scam and Fraud
Detection system.

Your job is to analyze evidence produced by Gates 1-4.

You MUST follow these rules:

1. Do not invent facts.
2. Do not perform new external verification.
3. Use only the evidence supplied by Gates 1-4.
4. Clearly distinguish strong evidence from weak evidence.
5.  A missing piece of information means UNKNOWN, not fraudulent.
   Never treat missing company names, email addresses, URLs, recruiter
   details, or verification data as scam evidence by themselves.
   UNKNOWN evidence may reduce confidence but must not independently
   justify a SUSPICIOUS assessment.
6. Do not automatically trust or reject the ML prediction.
7. Consider contradictions between different gates.
8. Keep the reasoning concise and understandable to a normal user.
9. Produce exactly 4-5 reasoning points.
10. Produce exactly 4-5 practical recommendations.
11. Recommendations must be appropriate for the assessment.
12. Never claim a company is fraudulent solely because a generic email
    provider was used.
13. 13. Never mention "Gate 1", "Gate 2", "Gate 3", "Gate 4", or "Gate 5"
    in reasoning, recommendations, supporting evidence,
    contradicting evidence, or warnings.
    Never claim a domain is fake solely because it could not be reached.
    Explain findings directly in user-friendly language.
14. The assessment must be one of:
    SUSPICIOUS
    NOT_SUSPICIOUS
    INCONCLUSIVE

Assessment guidance:

SUSPICIOUS:
Use SUSPICIOUS only when the supplied evidence contains meaningful indicators
of potential fraud.

Strong scam indicators from the extracted input should generally carry more
weight than weak or generic signals.

Examples of strong indicators include:
- upfront payment or registration fee requests
- requests for OTPs, passwords, or sensitive financial information
- suspicious payment instructions
- impersonation indicators
- major contradictions between recruiter/company/domain information
- clearly suspicious contact or application behavior
- multiple independent scam indicators occurring together

Do not classify something as SUSPICIOUS solely because information is missing,
verification is UNKNOWN, the message is generic, or the ML model predicts
LEGITIMATE/SCAM.

NOT_SUSPICIOUS:
Use NOT_SUSPICIOUS when the available evidence is reasonably consistent with
a legitimate opportunity and there are no meaningful scam indicators or major
contradictions.

However, NOT_SUSPICIOUS does not mean guaranteed legitimate or guaranteed safe.

Do not use NOT_SUSPICIOUS merely because:
- the company is well known
- the domain is legitimate
- the ML model predicts LEGITIMATE
- no scam indicators were detected

Consider the overall available evidence.

INCONCLUSIVE:
Use when there is insufficient information to confidently classify the
opportunity, especially when important verification information is
missing or Gates 1-4 contain mostly UNKNOWN results without strong scam
signals.

Do not convert uncertainty into suspicion.

Missing information is UNKNOWN, not scam evidence.

Do not classify an opportunity as SUSPICIOUS merely because:
- company information is missing
- recruiter information is missing
- email is missing
- URL is missing
- domain verification is unavailable
- job details are incomplete

If important information is missing and there are no actual scam indicators,
prefer INCONCLUSIVE.


When describing machine-learning output, do not present the model's probability
as a factual probability that the job is legitimate or fraudulent.

Describe it as model confidence or model prediction instead.

For example:
"The machine learning model classified the available content as legitimate
with high model confidence."

Never say:
"This job has a 100% probability of being legitimate."

Do not treat confidence as a probability that the job is legally or
factually fraudulent. It represents confidence in this assessment based
only on the supplied evidence.

The machine-learning prediction is supporting evidence only.
Do not treat a high-confidence ML prediction as conclusive by itself.

If the ML prediction strongly conflicts with strong website/domain
verification, investigate the nature of the input before relying on the
ML prediction.

For example, a legitimate careers or company webpage may contain
language that differs significantly from the job-scam training data.
A conflicting ML prediction on such content should reduce confidence
rather than automatically make the opportunity suspicious.

Never classify an opportunity as SUSPICIOUS solely because the ML model
predicts FRAUDULENT.

Do not claim that an opportunity is definitely safe, genuine, or free from fraud.

When no scam indicators are found, say:
"No scam indicators were detected in the available content."

Do not say:
"There is no evidence of fraudulent activity associated with this job."

Absence of detected evidence does not prove legitimacy.

When a URL belongs to an official company domain, distinguish between
"the website/domain appears legitimate" and "the job opportunity is legitimate."

A legitimate company domain does not automatically make every job,
recruiter, email, or communication legitimate.

For example:
"The URL belongs to the company's official domain and the available
webpage content is consistent with its careers site."

Do not conclude that the specific job or recruiter is guaranteed legitimate
solely because the domain is legitimate.

If the input is primarily a company careers homepage or general careers page,
assess the supplied website evidence rather than claiming that a specific job
opportunity has been verified.

If no specific job posting, recruiter, company contact, or job-specific details
are available, acknowledge that limitation.

Treat verification results according to their status:

VERIFIED:
Supports consistency with the claimed company/domain/recruiter.

NOT_VERIFIED or contradictory evidence:
May increase concern when the contradiction is meaningful.

UNKNOWN:
Means the system could not establish the fact.
UNKNOWN must not independently be treated as negative evidence.

"""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_prompt(
    investigation_input: Any,
    gate1_result: dict[str, Any],
    gate2_result: dict[str, Any],
    gate3_result: dict[str, Any],
    gate4_result: dict[str, Any],
) -> str:
    """Build the evidence package sent to Gemini."""
    evidence_package = {
        "investigation_input": {
            "extracted_text": getattr(
                investigation_input,
                "extracted_text",
                "",
            ),
            "company_names": getattr(
                investigation_input,
                "company_names",
                [],
            ),
            "email_addresses": getattr(
                investigation_input,
                "email_addresses",
                [],
            ),
            "urls": getattr(
                investigation_input,
                "urls",
                [],
            ),
        },
        "gate_1": gate1_result,
        "gate_2": gate2_result,
        "gate_3": gate3_result,
        "gate_4": gate4_result,
    }

    return f"""
Analyze the following investigation evidence.

IMPORTANT:
The evidence below is authoritative for this reasoning step.
Do not invent missing information.

Return a structured assessment containing:

* assessment
* confidence
* reasoning
* recommendations
* supporting_evidence
* contradicting_evidence
* warnings

The reasoning MUST contain 4-5 concise points explaining WHY the
assessment was reached.

The recommendations MUST contain 4-5 concise, practical points explaining
WHAT the user should do next.

Keep each reasoning point and recommendation reasonably short.

Evidence package:

{json.dumps(evidence_package, indent=2, ensure_ascii=False, default=str)}
"""


def _generate_with_retry(
    client: genai.Client,
    model_name: str,
    prompt: str,
    response_schema: dict[str, Any],
):
    """Call Gemini with retries for temporary server failures."""
    last_error: Exception | None = None

    for attempt in range(MAX_RETRIES):
        try:
            return client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION,
                    response_mime_type="application/json",
                    response_schema=response_schema,
                    temperature=0.2,
                    max_output_tokens=4000,
                ),
            )
        except Exception as exc:
            last_error = exc
            error_text = str(exc)

            # Retry temporary Google/Gemini availability failures.
            if "503" not in error_text and "UNAVAILABLE" not in error_text:
                raise

            if attempt < MAX_RETRIES - 1:
                delay = RETRY_DELAY_SECONDS * (2**attempt)
                time.sleep(delay)

    raise RuntimeError(
        f"Gemini service remained unavailable after {MAX_RETRIES} attempts."
    ) from last_error


# ---------------------------------------------------------------------------
# Main Gate 5 Function
# ---------------------------------------------------------------------------


def analyze_with_llm(
    investigation_input: Any,
    gate1_result: dict[str, Any],
    gate2_result: dict[str, Any],
    gate3_result: dict[str, Any],
    gate4_result: dict[str, Any],
    model_name: str = DEFAULT_MODEL,
) -> LLMAnalysisResult:
    """Run Gate 5 evidence reasoning using Gemini."""
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise RuntimeError("GEMINI_API_KEY environment variable is not set.")

    client = genai.Client(api_key=api_key)

    prompt = _build_prompt(
        investigation_input=investigation_input,
        gate1_result=gate1_result,
        gate2_result=gate2_result,
        gate3_result=gate3_result,
        gate4_result=gate4_result,
    )

    response_schema = {
        "type": "object",
        "properties": {
            "assessment": {
                "type": "string",
                "enum": [
                    "SUSPICIOUS",
                    "NOT_SUSPICIOUS",
                    "INCONCLUSIVE",
                ],
            },
            "confidence": {
                "type": "number",
            },
            "reasoning": {
                "type": "array",
                "items": {"type": "string"},
            },
            "recommendations": {
                "type": "array",
                "items": {"type": "string"},
            },
            "supporting_evidence": {
                "type": "array",
                "items": {"type": "string"},
            },
            "contradicting_evidence": {
                "type": "array",
                "items": {"type": "string"},
            },
            "warnings": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
        "required": [
            "assessment",
            "confidence",
            "reasoning",
            "recommendations",
            "supporting_evidence",
            "contradicting_evidence",
            "warnings",
        ],
    }

    response = _generate_with_retry(
        client=client,
        model_name=model_name,
        prompt=prompt,
        response_schema=response_schema,
    )

    if not response.text:
        raise RuntimeError("Gemini returned an empty response.")

    print("\n" + "=" * 70)
    print("RAW GEMINI RESPONSE")
    print("=" * 70)
    print(response.text)
    print("=" * 70 + "\n")

    try:
        result = json.loads(response.text)

    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "Gemini returned invalid JSON. "
            f"Raw response: {response.text[:1000]}"
        ) from exc

    # ---------------------------------------------------------
    # Assessment
    # ---------------------------------------------------------

    assessment = str(
        result.get(
            "assessment",
            "INCONCLUSIVE"
        )
    ).upper()

    if assessment not in {
        "SUSPICIOUS",
        "NOT_SUSPICIOUS",
        "INCONCLUSIVE",
    }:
        assessment = "INCONCLUSIVE"

    # ---------------------------------------------------------
    # Confidence
    # ---------------------------------------------------------

    try:
        confidence = float(
            result.get(
                "confidence",
                0.0
            )
        )

    except (TypeError, ValueError):
        confidence = 0.0

    confidence = max(
        0.0,
        min(1.0, confidence)
    )

    # ---------------------------------------------------------
    # Structured lists
    # ---------------------------------------------------------

    reasoning = result.get(
        "reasoning",
        []
    )

    recommendations = result.get(
        "recommendations",
        []
    )

    supporting_evidence = result.get(
        "supporting_evidence",
        []
    )

    contradicting_evidence = result.get(
        "contradicting_evidence",
        []
    )

    warnings = result.get(
        "warnings",
        []
    )

    # ---------------------------------------------------------
    # Ensure list types
    # ---------------------------------------------------------

    if not isinstance(reasoning, list):
        reasoning = []

    if not isinstance(recommendations, list):
        recommendations = []

    if not isinstance(supporting_evidence, list):
        supporting_evidence = []

    if not isinstance(contradicting_evidence, list):
        contradicting_evidence = []

    if not isinstance(warnings, list):
        warnings = []

    # ---------------------------------------------------------
    # Final result
    # ---------------------------------------------------------

    return LLMAnalysisResult(
        assessment=assessment,
        confidence=confidence,
        reasoning=[
            str(item)
            for item in reasoning
        ][:5],

        recommendations=[
            str(item)
            for item in recommendations
        ][:5],

        supporting_evidence=[
            str(item)
            for item in supporting_evidence
        ],

        contradicting_evidence=[
            str(item)
            for item in contradicting_evidence
        ],

        warnings=[
            str(item)
            for item in warnings
        ],

        model_name=model_name,
    )


__all__ = [
    "LLMAnalysisResult",
    "analyze_with_llm",
]
