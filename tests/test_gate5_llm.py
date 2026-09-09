import os

from agent.nodes.gate5_llm import analyze_with_llm
from agent.nodes.input_processor import InvestigationInput


def test_gate5_llm_reasoning():
    """Test Gate 5 with a realistic suspicious job investigation."""

    if not os.getenv("GEMINI_API_KEY"):
        raise RuntimeError("GEMINI_API_KEY is not configured.")

    raw_text = (
        "Congratulations! You have been selected for a Data Entry "
        "work-from-home position. To confirm your employment, you must "
        "pay a refundable registration fee of Rs 2500 through UPI. "
        "Contact the recruiter at hiringdesk2026@gmail.com."
    )

    investigation_input = InvestigationInput(
        source_type="text",
        raw_text=raw_text,
        extracted_text=raw_text,
        company_names=["ABC Technologies"],
        email_addresses=["hiringdesk2026@gmail.com"],
        urls=[],
    )

    gate1_result = {
        "signals": [
            {
                "signal": "UPFRONT_PAYMENT_REQUEST",
                "severity": "HIGH",
            },
            {
                "signal": "GENERIC_RECRUITER_EMAIL",
                "severity": "MEDIUM",
            },
        ],
        "risk_score": 0.95,
    }

    gate2_result = {
        "prediction": "FRAUD",
        "probability": 0.96,
        "model_name": "GaussianNB",
        "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
    }

    gate3_result = {
        "company_verification": {
            "status": "SUSPICIOUS",
            "evidence": [
                "Company name does not appear consistent "
                "with the supplied recruiter domain."
            ],
        },
        "recruiter_verification": {
            "status": "SUSPICIOUS",
            "evidence": [
                "Recruiter uses a generic email provider."
            ],
        },
        "domain_verification": {
            "status": "UNKNOWN",
            "evidence": [
                "No company website was supplied."
            ],
        },
    }

    gate4_result = {
        "query": "job registration fee UPI recruiter payment scam",
        "results": [
            {
                "text": (
                    "Fake recruitment scams frequently request "
                    "registration or processing fees through UPI "
                    "before employment."
                ),
                "score": 0.91,
            }
        ],
    }

    result = analyze_with_llm(
        investigation_input=investigation_input,
        gate1_result=gate1_result,
        gate2_result=gate2_result,
        gate3_result=gate3_result,
        gate4_result=gate4_result,
    )

    assert result.assessment in {
        "SUSPICIOUS",
        "NOT_SUSPICIOUS",
        "INCONCLUSIVE",
    }

    assert 0.0 <= result.confidence <= 1.0

    assert 4 <= len(result.reasoning) <= 5
    assert 4 <= len(result.recommendations) <= 5

    assert isinstance(result.supporting_evidence, list)
    assert isinstance(result.contradicting_evidence, list)
    assert isinstance(result.warnings, list)

    assert result.model_name == "gemini-2.5-flash"

    print("\nGate 5 assessment:", result.assessment)
    print("Confidence:", result.confidence)

    print("\nReasoning:")
    for item in result.reasoning:
        print("-", item)

    print("\nRecommendations:")
    for item in result.recommendations:
        print("-", item)
