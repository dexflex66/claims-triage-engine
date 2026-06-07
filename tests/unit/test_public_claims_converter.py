import json
from pathlib import Path

from scripts.convert_public_claims_to_shadow import convert_csv_to_shadow_jsonl


def _read_jsonl(path: Path):
    out = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def test_convert_public_claims_csv_to_shadow_jsonl(tmp_path):
    src = tmp_path / "synthea_like.csv"
    src.write_text(
        "PATIENT,DIAGNOSIS1,PROCEDURE1,CLINICIAN,PAYER,DESCRIPTION,PAID_AMOUNT\n"
        "P-1,M54.5,72148,1234567890,BCBS,Low back pain,100.00\n"
        "P-2,M25.5,73721,2234567890,AETNA,Knee pain,0.00\n",
        encoding="utf-8",
    )
    out = tmp_path / "shadow.jsonl"

    summary = convert_csv_to_shadow_jsonl(
        input_csv=src,
        output_jsonl=out,
        preset="synthea",
        country="US",
        default_payer_id="BCBS",
        case_prefix="PUB",
        provenance="CLINICAL_NOTE_V1",
        max_rows=0,
        allow_fallbacks=True,
    )

    assert summary["rows_written"] == 2
    rows = _read_jsonl(out)
    assert len(rows) == 2
    assert rows[0]["compile_request"]["fields"]["patient_id"] == "P-1"
    assert rows[0]["compile_request"]["fields"]["provider_npi"] == "1234567890"
    assert rows[0]["expected_outcome"] == "approved"
    assert rows[1]["expected_outcome"] == "denied"
