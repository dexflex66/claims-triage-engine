import os
import pytest

quest_available = bool(os.environ.get("QUEST_ROOT"))

pytestmark = pytest.mark.skipif(
    not quest_available,
    reason="requires QUEST_ROOT env var pointing to QuEST core",
)


def test_compile_case_deterministic():
    from compiler import compile_case, load_policy

    policy = load_policy("policy/claims_policy_us.yaml")
    fields = {
        "patient_id": "P001",
        "diagnosis_code": "M54.5",
        "procedure_code": "72148",
        "provider_npi": "1234567890",
        "clinical_indication": "Low back pain",
    }
    evidence = [{"field": k, "value": v, "provenance": "CLINICAL_NOTE_V1"} for k, v in fields.items()]
    out1 = compile_case(fields, evidence, policy=policy)
    out2 = compile_case(fields, evidence, policy=policy)
    assert out1["decision_kind"] == out2["decision_kind"]
    assert out1["reasons"] == out2["reasons"]
