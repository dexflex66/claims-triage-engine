from service.policy import normalize_evidence_provenance


def test_normalize_evidence_provenance_maps_prefix_and_alias():
    evidence = [
        {"field": "patient_id", "value": "P1", "provenance": "CMS_SYNPUF_CARRIER_1A"},
        {"field": "diagnosis_code", "value": "M54.5", "provenance": "EHR_NOTE"},
        {"field": "procedure_code", "value": "72148", "provenance": "ORDER_FORM"},
    ]

    normalized, remapped = normalize_evidence_provenance("US", evidence)

    assert remapped == 3
    assert normalized[0]["provenance"] == "CLINICAL_NOTE_V1"
    assert normalized[1]["provenance"] == "CLINICAL_NOTE_V1"
    assert normalized[2]["provenance"] == "CLAIM_FORM_PDF_V1"
    assert normalized[0]["provenance_original"] == "CMS_SYNPUF_CARRIER_1A"
    assert normalized[1]["provenance_original"] == "EHR_NOTE"
    assert normalized[2]["provenance_original"] == "ORDER_FORM"


def test_normalize_evidence_provenance_no_change_for_known_source():
    evidence = [{"field": "patient_id", "value": "P1", "provenance": "CLINICAL_NOTE_V1"}]
    normalized, remapped = normalize_evidence_provenance("US", evidence)
    assert remapped == 0
    assert normalized[0]["provenance"] == "CLINICAL_NOTE_V1"
    assert "provenance_original" not in normalized[0]
