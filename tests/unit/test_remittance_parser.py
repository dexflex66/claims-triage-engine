from local_claims_core import parse_835_text, parse_era_json


def test_parse_era_json():
    parsed = parse_era_json(
        {
            "remittance_id": "R1",
            "case_id": "C1",
            "submission_id": "S1",
            "external_ref": "E1",
            "adjudication_status": "paid",
            "paid_amount": 120.5,
            "allowed_amount": 140.0,
            "denial_codes": [],
            "payer_claim_id": "PCLM-1",
            "timestamp_utc": "2026-02-17T00:00:00Z",
        }
    )
    assert parsed.adjudication_status == "approved"
    assert parsed.paid_amount == 120.5


def test_parse_835_text():
    raw = "REMIT|R2|C2|S2|E2|denied|0|100|CO-45,CO-96|PCLM-2|2026-02-17T00:00:00Z"
    parsed = parse_835_text(raw)
    assert parsed.remittance_id == "R2"
    assert parsed.adjudication_status == "denied"
    assert parsed.denial_codes == ["CO-45", "CO-96"]
