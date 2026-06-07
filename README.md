# Payer-Proof Claims Automation

Production-oriented service for general radiology prior authorization (US + India) with policy-to-evidence traceability, human-in-the-loop review, deterministic submission flow, and closed-loop learning.

## What It Does

- Compiles claim cases against policy (QuEST decision core).
- Builds citation-backed approval packets.
- Queues abstained/flagged cases for review.
- Submits via connector abstraction (US 278/837 path, India pre-auth path).
- Tracks status/reconciliation/outcomes in Postgres.
- Exposes audit events and KPI snapshots.

## Architecture

- `service/` — FastAPI app, routes, security, schemas.
- `db/` — SQLAlchemy models/session and migrations.
- `connectors/` — submission adapter interface and country connectors.
- `repositories/` — DB persistence layer.
- `core/` — compiler bridge and workflow logic with compatibility fallbacks.
- `compliance/` — RBAC, audit event utilities, retention policy.
- `jobs/` — reconciliation, status polling, retention, playbook refresh.

## API Surface

- `POST /v1/cases/compile`
- `POST /v1/cases/{case_id}/review/approve`
- `POST /v1/cases/{case_id}/review/reject`
- `POST /v1/cases/{case_id}/submit`
- `GET /v1/cases/{case_id}/status`
- `POST /v1/remittance/ingest`
- `GET /v1/cases/{case_id}/remittance`
- `POST /v1/cases/{case_id}/payment/post`
- `GET /v1/cases/{case_id}/payment/posts`
- `POST /v1/cases/{case_id}/outcome`
- `GET /v1/queues/review`
- `GET /v1/reconciliation/sent-not-received`
- `GET /v1/ops/sla`
- `GET /v1/ops/controls`
- `GET /v1/audit/events`
- `GET /v1/metrics/kpis`
- `GET /metrics` (Prometheus format)

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Optional env
export APP_ENV="dev"
export DATABASE_URL="sqlite:///./payer_proof_claims.db"
export OIDC_AUDIENCE="payer-proof-claims"
export OIDC_REQUIRE_SIGNATURE="false"
export OIDC_JWKS_URL=""
export OIDC_JWKS_JSON=""
export ALLOW_STUB_CONNECTORS="true"

# Optional live US278 transport
export US278_BASE_URL="https://your-clearinghouse.example"
export US278_SUBMIT_PATH="/api/v1/prior-auth/submit"
export US278_STATUS_PATH_TEMPLATE="/api/v1/prior-auth/{external_ref}/status"
export US278_RECEIPT_PATH_TEMPLATE="/api/v1/prior-auth/{external_ref}/receipt"
export US278_AUTH_MODE="bearer_hmac"
export US278_API_TOKEN=""
export US278_HMAC_SECRET=""
export US278_HMAC_KEY_ID=""
export US278_ENFORCE_CONTRACT="true"
export US278_MAX_RETRIES="3"
export US278_BACKOFF_SECONDS="0.5"
export US278_TIMEOUT_SECONDS="10"

# Optional live India preauth transport
export IN_PREAUTH_BASE_URL="https://your-india-insurer.example"
export IN_PREAUTH_SUBMIT_PATH="/api/v1/preauth/submit"
export IN_PREAUTH_STATUS_PATH_TEMPLATE="/api/v1/preauth/{external_ref}/status"
export IN_PREAUTH_RECEIPT_PATH_TEMPLATE="/api/v1/preauth/{external_ref}/receipt"
export IN_PREAUTH_AUTH_MODE="bearer_hmac"
export IN_PREAUTH_API_TOKEN=""
export IN_PREAUTH_HMAC_SECRET=""
export IN_PREAUTH_HMAC_KEY_ID=""
export IN_PREAUTH_ENFORCE_CONTRACT="true"
export IN_PREAUTH_MAX_RETRIES="3"
export IN_PREAUTH_BACKOFF_SECONDS="0.5"
export IN_PREAUTH_TIMEOUT_SECONDS="10"

# Optional payment rails (live mode activates when *_BASE_URL is set)
export ACH_POST_BASE_URL=""
export ACH_POST_API_TOKEN=""
export VCARD_POST_BASE_URL=""
export VCARD_POST_API_TOKEN=""
export ERP_POST_BASE_URL=""
export ERP_POST_API_TOKEN=""

# Optional transport + security controls
export MTLS_REQUIRED="false"
export TLS_CLIENT_CA_CERT_PATH=""
export TLS_SERVER_CERT_PATH=""
export TLS_SERVER_KEY_PATH=""
export KEY_ROTATION_ENFORCED="false"
export US278_ACTIVE_KEY_ID=""
export US278_ALLOWED_KEY_IDS=""
export IP_ALLOWLIST_ENABLED="false"
export IP_ALLOWLIST_CIDRS="10.0.0.0/8,192.168.0.0/16"

# Optional logs
export LOG_JSON="true"
export LOG_LEVEL="INFO"

python scripts/apply_migrations.py
uvicorn service.main:app --reload
```

Validate live connector config before startup:

```bash
python scripts/validate_live_contract.py --contract us_278_837
python scripts/validate_live_contract.py --contract india_preauth
```

## Auth

Bearer JWT is required for API endpoints.

- Set `OIDC_REQUIRE_SIGNATURE=true` to enforce signed-token verification.
- Signature mode validates JWT signature against JWKS from `OIDC_JWKS_URL` or `OIDC_JWKS_JSON`.
- Default mode validates token structure/claims (`aud`, `exp`, optional `nbf`) for local and test use.
- Supported roles: `viewer`, `reviewer`, `ops_submitter`, `admin`.

## Data and Migration

- Schema models in `db/models.py`.
- SQL migrations in `db/migrations/`.
- Apply migrations with:

```bash
python scripts/apply_migrations.py
python scripts/db_readiness.py
```

- DB backup/restore scripts:
  - `python scripts/db_backup.py --out backups/pre_release.dump`
  - `python scripts/db_restore.py --in backups/pre_release.dump --clean`
- Full DB runbook: `/Users/mayank/Downloads/payer_proof_claims/db/PRODUCTION_RUNBOOK.md`

## Deployment

- Container image: `/Users/mayank/Downloads/payer_proof_claims/Dockerfile`
- Local stack (app + Postgres): `/Users/mayank/Downloads/payer_proof_claims/docker-compose.yml`
- CI workflow: `/Users/mayank/Downloads/payer_proof_claims/.github/workflows/ci.yml`

Quick start:

```bash
make docker-build
make docker-up
```

## Compatibility

Legacy JSONL paths under `data/` are still written by core modules for one transition release while DB-backed repositories are active.

## Testing

```bash
pytest -q
```

## Golden Fixtures

Reusable fixture packs are available for both regions:

- `/Users/mayank/Downloads/payer_proof_claims/fixtures/us/compile_request.json`
- `/Users/mayank/Downloads/payer_proof_claims/fixtures/us/remittance_approved.json`
- `/Users/mayank/Downloads/payer_proof_claims/fixtures/us/payment_post_request.json`
- `/Users/mayank/Downloads/payer_proof_claims/fixtures/in/compile_request.json`
- `/Users/mayank/Downloads/payer_proof_claims/fixtures/in/remittance_approved.json`
- `/Users/mayank/Downloads/payer_proof_claims/fixtures/in/payment_post_request.json`

These are used by smoke tests and can be copied into staging runbooks.

## Sandboxless Local Integration

Use the bundled mock clearinghouse when no payer sandbox is available:

```bash
python scripts/run_mock_clearinghouse.py --host 127.0.0.1 --port 8089
```

Then point the US connector to the mock:

```bash
export US278_BASE_URL="http://127.0.0.1:8089"
python scripts/smoke_us_connector.py
```

Contract tests validate submit/status/receipt/idempotency against this mock:

```bash
pytest -q tests/integration/test_mock_clearinghouse_contract.py
```

Mock smoke for India connector:

```bash
python scripts/smoke_in_connector.py
```

## One-Command Staging Smoke

Run complete no-spend flow and write a summary JSON:

```bash
python scripts/staging_smoke.py --dataset us --output artifacts/staging_smoke_us.json
python scripts/staging_smoke.py --dataset in --output artifacts/staging_smoke_in.json
```

This executes compile -> submit -> status -> remittance ingest -> payment post.

## Shadow Replay (Real/Historical Data, No External Spend)

Replay historical cases through local compile/review/submit/status/outcome flow:

```bash
python scripts/shadow_replay.py \
  --input fixtures/shadow/historical_cases.jsonl \
  --output-csv artifacts/shadow_replay_rows.csv \
  --output-summary artifacts/shadow_replay_summary.json
```

Supported input formats: `.jsonl`, `.json`, `.csv`.

Record schema options:
- `compile_request` object with full compile payload + optional `expected_outcome`
- or flat columns/keys: `case_id`, `country`, `payer_id`, `fields`, `evidence`, `expected_outcome`
- or CSV `field_*` columns if `fields` is not provided

### Convert Public/Synthetic CSV -> Shadow JSONL

Use this to turn Synthea/CMS-like CSV into replay-ready JSONL:

```bash
python scripts/convert_public_claims_to_shadow.py \
  --input data/public_claims.csv \
  --output fixtures/shadow/public_replay.jsonl \
  --preset auto \
  --country US \
  --default-payer-id BCBS
```

Then replay:

```bash
python scripts/shadow_replay.py \
  --input fixtures/shadow/public_replay.jsonl \
  --output-csv artifacts/public_replay_rows.csv \
  --output-summary artifacts/public_replay_summary.json
```

## Observability

- Structured request logs are enabled by default (`LOG_JSON=true`).
- Prometheus metrics available at `GET /metrics`.
- KPI snapshots available at `GET /v1/metrics/kpis`.

## Production Security Guardrails

When `APP_ENV=production`, startup fails if required controls are not enabled:
- Signed OIDC (`OIDC_REQUIRE_SIGNATURE=true` + JWKS source)
- mTLS (`MTLS_REQUIRED=true`)
- IP allowlist (`IP_ALLOWLIST_ENABLED=true`)
- Key rotation (`KEY_ROTATION_ENFORCED=true`)
- Connector contracts enforced
- `ALLOW_STUB_CONNECTORS=false`
- PostgreSQL `DATABASE_URL`

Manual control check:

```bash
python scripts/run_control_checks.py
```

## UAT and Rollback

- Live UAT runner:
  - `python scripts/run_live_uat.py --base-url https://<api-host> --token <jwt> --dataset us`
  - `python scripts/run_live_uat.py --base-url https://<api-host> --token <jwt> --dataset in`
- Rollback drill:
  - `python scripts/run_rollback_drill.py --primary-db-url postgresql+psycopg://... --backup-out backups/drill.dump --restore-db-url postgresql+psycopg://... --clean-restore`
- Runbook: `/Users/mayank/Downloads/payer_proof_claims/operations/UAT_ROLLBACK_RUNBOOK.md`

## Compliance Gate

Fail-closed go-live gate:

```bash
python scripts/compliance_gate.py
```

Checklist:
- `/Users/mayank/Downloads/payer_proof_claims/compliance/GO_LIVE_LEGAL_CHECKLIST.md`

## Scope Note

This service optimizes prior-auth approval workflow and revenue realization quality. It does not directly initiate fund transfers.
