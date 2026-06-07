from local_claims_core import validate_packet_citations


def test_validate_packet_citations_flags_missing_citation():
    packet = {
        "sections": [
            {
                "criterion": "diagnosis_code",
                "policy_clause_ref": "policy.required.diagnosis_code",
                "satisfied": True,
                "chart_citations": [],
            }
        ]
    }
    errors = validate_packet_citations(packet)
    assert "missing_chart_citation:diagnosis_code" in errors
