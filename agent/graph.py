"""Main investigation pipeline.

Current pipeline:
Input → Gate 1 → Gate 2 → Gate 3 → Gate 4 → Gate 5

Gate 5 performs LLM-based evidence reasoning.

Important:
This graph orchestrates the investigation gates.
It does not make the final deterministic scam/legitimate decision.
"""

from __future__ import annotations

from typing import Any

from .nodes.input_processor import InvestigationInput
from .nodes.gate1_flag_extractor import extract_signals
from .nodes.gate2_ml_analyzer import analyze_with_ml
from .nodes.gate3_verifier import verify_company_recruiter_domain
from .nodes.gate4_rag import run_gate4
from .nodes.gate5_llm import analyze_with_llm


def run_investigation(
    investigation_input: InvestigationInput,
) -> dict[str, Any]:
    """Run the investigation pipeline through Gate 5.

    Gates:
        Gate 1 → Hard scam-signal extraction
        Gate 2 → ML / NLP analysis
        Gate 3 → Company + Recruiter + Domain verification
        Gate 4 → RAG / semantic retrieval
        Gate 5 → LLM evidence reasoning

    No final deterministic verdict is produced here.
    """

    # =========================================================
    # GATE 1
    # Hard scam-signal extraction
    # =========================================================

    gate1_result = extract_signals(
        investigation_input
    )

    # =========================================================
    # GATE 2
    # ML / NLP analysis
    # =========================================================

    gate2_result = analyze_with_ml(
        investigation_input
    )

    # =========================================================
    # GATE 3
    # Company + Recruiter + Domain verification
    # =========================================================

    gate3_result = verify_company_recruiter_domain(
        investigation_input
    )

    # =========================================================
    # GATE 4
    # RAG / Semantic Retrieval
    # =========================================================

    gate4_result = run_gate4(
        investigation_input,
        top_k=5,
    )

    # =========================================================
    # GATE 5
    # LLM Evidence Reasoning
    # =========================================================

    gate5_result = analyze_with_llm(
        investigation_input=investigation_input,
        gate1_result=gate1_result.to_dict(),
        gate2_result=gate2_result.to_dict(),
        gate3_result={
            "company_verification": {
                "status": (
                    gate3_result
                    .company_verification
                    .status.value
                ),
                "evidence": (
                    gate3_result
                    .company_verification
                    .evidence
                ),
                "source": (
                    gate3_result
                    .company_verification
                    .source
                ),
                "confidence": (
                    gate3_result
                    .company_verification
                    .confidence
                ),
                "warnings": (
                    gate3_result
                    .company_verification
                    .warnings
                ),
                "metadata": (
                    gate3_result
                    .company_verification
                    .metadata
                ),
            },
            "recruiter_verification": {
                "status": (
                    gate3_result
                    .recruiter_verification
                    .status.value
                ),
                "evidence": (
                    gate3_result
                    .recruiter_verification
                    .evidence
                ),
                "source": (
                    gate3_result
                    .recruiter_verification
                    .source
                ),
                "confidence": (
                    gate3_result
                    .recruiter_verification
                    .confidence
                ),
                "warnings": (
                    gate3_result
                    .recruiter_verification
                    .warnings
                ),
                "metadata": (
                    gate3_result
                    .recruiter_verification
                    .metadata
                ),
            },
            "domain_verification": {
                "status": (
                    gate3_result
                    .domain_verification
                    .status.value
                ),
                "evidence": (
                    gate3_result
                    .domain_verification
                    .evidence
                ),
                "source": (
                    gate3_result
                    .domain_verification
                    .source
                ),
                "confidence": (
                    gate3_result
                    .domain_verification
                    .confidence
                ),
                "warnings": (
                    gate3_result
                    .domain_verification
                    .warnings
                ),
                "metadata": (
                    gate3_result
                    .domain_verification
                    .metadata
                ),
            },
        },
        gate4_result=gate4_result.to_dict(),
    )

    # =========================================================
    # Return complete evidence
    # =========================================================

    return {
        "gate_1": gate1_result.to_dict(),

        "gate_2": gate2_result.to_dict(),

        "gate_3": {
            "company_verification": {
                "status": (
                    gate3_result
                    .company_verification
                    .status.value
                ),
                "evidence": (
                    gate3_result
                    .company_verification
                    .evidence
                ),
                "source": (
                    gate3_result
                    .company_verification
                    .source
                ),
                "confidence": (
                    gate3_result
                    .company_verification
                    .confidence
                ),
                "warnings": (
                    gate3_result
                    .company_verification
                    .warnings
                ),
                "metadata": (
                    gate3_result
                    .company_verification
                    .metadata
                ),
            },

            "recruiter_verification": {
                "status": (
                    gate3_result
                    .recruiter_verification
                    .status.value
                ),
                "evidence": (
                    gate3_result
                    .recruiter_verification
                    .evidence
                ),
                "source": (
                    gate3_result
                    .recruiter_verification
                    .source
                ),
                "confidence": (
                    gate3_result
                    .recruiter_verification
                    .confidence
                ),
                "warnings": (
                    gate3_result
                    .recruiter_verification
                    .warnings
                ),
                "metadata": (
                    gate3_result
                    .recruiter_verification
                    .metadata
                ),
            },

            "domain_verification": {
                "status": (
                    gate3_result
                    .domain_verification
                    .status.value
                ),
                "evidence": (
                    gate3_result
                    .domain_verification
                    .evidence
                ),
                "source": (
                    gate3_result
                    .domain_verification
                    .source
                ),
                "confidence": (
                    gate3_result
                    .domain_verification
                    .confidence
                ),
                "warnings": (
                    gate3_result
                    .domain_verification
                    .warnings
                ),
                "metadata": (
                    gate3_result
                    .domain_verification
                    .metadata
                ),
            },
        },

        "gate_4": gate4_result.to_dict(),

        "gate_5": gate5_result.to_dict(),
    }


__all__ = [
    "run_investigation",
]