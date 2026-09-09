from agent.graph import run_investigation
from agent.nodes.input_processor import InvestigationInput, SourceType


def test_pipeline_through_gate4():
    text = """
    Congratulations! You have been selected for a work-from-home job.
    No interview is required.
    Please contact our recruiter on WhatsApp.
    Pay a refundable security deposit of ₹2500 through UPI before joining.
    """

    investigation_input = InvestigationInput(
        source_type=SourceType.TEXT,
        raw_text=text,
        extracted_text=text,
        urls=[],
        email_addresses=[],
        phone_numbers=[],
        company_names=[],
        recruiter_names=[],
        job_titles=[],
        locations=[],
        salary_mentions=[],
    )

    result = run_investigation(investigation_input)

    # Gates exist
    assert "gate_1" in result
    assert "gate_2" in result
    assert "gate_3" in result
    assert "gate_4" in result

    # Gate 4 completed
    assert result["gate_4"]["gate"] == "gate_4"
    assert result["gate_4"]["status"] == "completed"
    assert result["gate_4"]["method"] == "semantic_similarity"

    # RAG returned evidence
    evidence = result["gate_4"]["retrieved_evidence"]

    assert len(evidence) > 0
    assert len(evidence) <= 5

    # Every result has the expected structure
    for item in evidence:
        assert "document_id" in item
        assert "title" in item
        assert "scam_type" in item
        assert "content" in item
        assert "similarity" in item
        assert "source" in item

        assert isinstance(item["similarity"], float)