from agent.graph import run_investigation


class TestInput:
    extracted_text = """
    ABC Technologies is hiring Data Entry Operators.
    Selected candidates must pay a refundable registration fee of Rs 2500
    through UPI to confirm their employment.
    Contact: hiringdesk2026@gmail.com
    """

    company_names = ["ABC Technologies"]
    email_addresses = ["hiringdesk2026@gmail.com"]
    urls = []


def test_pipeline_through_gate5():
    result = run_investigation(TestInput())

    assert "gate_1" in result
    assert "gate_2" in result
    assert "gate_3" in result
    assert "gate_4" in result
    assert "gate_5" in result

    gate5 = result["gate_5"]

    assert gate5["assessment"] in {
        "SUSPICIOUS",
        "NOT_SUSPICIOUS",
        "INCONCLUSIVE",
    }

    assert 0.0 <= gate5["confidence"] <= 1.0

    assert isinstance(gate5["reasoning"], list)
    assert 4 <= len(gate5["reasoning"]) <= 5

    assert isinstance(gate5["recommendations"], list)
    assert 4 <= len(gate5["recommendations"]) <= 5

    assert isinstance(gate5["supporting_evidence"], list)
    assert isinstance(gate5["contradicting_evidence"], list)
    assert isinstance(gate5["warnings"], list)