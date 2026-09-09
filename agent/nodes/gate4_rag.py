"""Gate 4: RAG-based semantic investigation.

This gate retrieves semantically relevant evidence from the Indian
job-scam knowledge base.

Gate 4 does NOT:
- make a scam/legitimate decision
- calculate scam probability
- use keyword matching
- use regex
- use hardcoded scam rules
- call an LLM
- modify Gates 1-3
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from rag.retriever import RAGRetriever
from .input_processor import InvestigationInput


@dataclass
class RetrievedEvidence:
    """One semantically retrieved knowledge-base document."""

    document_id: str
    title: str
    scam_type: str
    content: str
    similarity: float
    source: str = "Indian job scam knowledge base"

    def to_dict(self) -> dict[str, Any]:
        return {
            "document_id": self.document_id,
            "title": self.title,
            "scam_type": self.scam_type,
            "content": self.content,
            "similarity": self.similarity,
            "source": self.source,
        }


@dataclass
class Gate4Result:
    """Structured output produced by Gate 4."""

    gate: str = "gate_4"
    status: str = "completed"
    method: str = "semantic_similarity"
    embedding_model: str = "all-MiniLM-L6-v2"
    top_k: int = 5
    retrieved_evidence: list[RetrievedEvidence] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "gate": self.gate,
            "status": self.status,
            "method": self.method,
            "embedding_model": self.embedding_model,
            "top_k": self.top_k,
            "retrieved_evidence": [
                evidence.to_dict() for evidence in self.retrieved_evidence
            ],
            "warnings": list(self.warnings),
        }


class Gate4RAG:
    """Semantic retrieval layer for Gate 4."""

    def __init__(self, top_k: int = 5) -> None:
        self.top_k = top_k
        self.retriever = RAGRetriever(top_k=top_k)

    def investigate(
        self,
        investigation_input: InvestigationInput,
    ) -> Gate4Result:
        text = investigation_input.extracted_text or ""

        if not text.strip():
            return Gate4Result(
                top_k=self.top_k,
                warnings=[
                    "No investigation text available for semantic retrieval."
                ],
            )

        results = self.retriever.retrieve(
            query=text,
            top_k=self.top_k,
        )

        evidence: list[RetrievedEvidence] = []

        for result in results:
            evidence.append(
                RetrievedEvidence(
                    document_id=str(result.get("document_id", "UNKNOWN")),
                    title=str(result.get("title", "Untitled document")),
                    scam_type=str(result.get("scam_type", "unknown")),
                    content=str(result.get("content", "")),
                    similarity=float(result.get("similarity_score", 0.0)),
                    source=str(
                        result.get("source", "Indian job scam knowledge base")
                    ),
                )
            )

        return Gate4Result(
            top_k=self.top_k,
            retrieved_evidence=evidence,
        )


def run_gate4(
    investigation_input: InvestigationInput,
    top_k: int = 5,
) -> Gate4Result:
    gate = Gate4RAG(top_k=top_k)
    return gate.investigate(investigation_input)


__all__ = [
    "RetrievedEvidence",
    "Gate4Result",
    "Gate4RAG",
    "run_gate4",
]