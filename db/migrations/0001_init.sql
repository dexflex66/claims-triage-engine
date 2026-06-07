-- Initial schema for payer_proof_claims v1
CREATE TABLE IF NOT EXISTS cases (
  id INTEGER PRIMARY KEY,
  case_id VARCHAR(128) UNIQUE NOT NULL,
  country VARCHAR(8) NOT NULL,
  payer_id VARCHAR(64) NOT NULL,
  fields JSON NOT NULL,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS case_evidence (
  id INTEGER PRIMARY KEY,
  case_id VARCHAR(128) NOT NULL,
  evidence JSON NOT NULL,
  created_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS compile_results (
  id INTEGER PRIMARY KEY,
  case_id VARCHAR(128) NOT NULL,
  decision_kind VARCHAR(32) NOT NULL,
  decision_code VARCHAR(64),
  result JSON NOT NULL,
  trace_id VARCHAR(64),
  created_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS review_queue (
  id INTEGER PRIMARY KEY,
  case_id VARCHAR(128) NOT NULL,
  packet JSON NOT NULL,
  status VARCHAR(32) NOT NULL,
  created_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS review_actions (
  id INTEGER PRIMARY KEY,
  case_id VARCHAR(128) NOT NULL,
  reviewer_id VARCHAR(128) NOT NULL,
  action VARCHAR(32) NOT NULL,
  note TEXT,
  timestamp_utc VARCHAR(64)
);

CREATE TABLE IF NOT EXISTS submissions (
  id INTEGER PRIMARY KEY,
  submission_id VARCHAR(128) UNIQUE NOT NULL,
  case_id VARCHAR(128) NOT NULL,
  method VARCHAR(64) NOT NULL,
  submission_channel VARCHAR(64),
  idempotency_key VARCHAR(128) NOT NULL,
  external_ref VARCHAR(256),
  proof_artifact_ref VARCHAR(512),
  handoff_notes TEXT,
  status VARCHAR(32) NOT NULL,
  retry_count INTEGER DEFAULT 0,
  submitted_at VARCHAR(64),
  last_error TEXT,
  UNIQUE(case_id, idempotency_key)
);

CREATE TABLE IF NOT EXISTS submission_status_history (
  id INTEGER PRIMARY KEY,
  case_id VARCHAR(128) NOT NULL,
  submission_id VARCHAR(128) NOT NULL,
  external_ref VARCHAR(256),
  status VARCHAR(32) NOT NULL,
  raw_payload JSON,
  timestamp_utc VARCHAR(64)
);

CREATE TABLE IF NOT EXISTS reconciliation_events (
  id INTEGER PRIMARY KEY,
  case_id VARCHAR(128) NOT NULL,
  event VARCHAR(64) NOT NULL,
  payload JSON,
  timestamp_utc VARCHAR(64)
);

CREATE TABLE IF NOT EXISTS outcomes (
  id INTEGER PRIMARY KEY,
  case_id VARCHAR(128) NOT NULL,
  outcome VARCHAR(32) NOT NULL,
  payer_id VARCHAR(64),
  procedure_code VARCHAR(64),
  diagnosis_code VARCHAR(64),
  reason_codes JSON,
  turnaround_days INTEGER,
  requested_addenda JSON,
  amount FLOAT,
  timestamp_utc VARCHAR(64)
);

CREATE TABLE IF NOT EXISTS remittances (
  id INTEGER PRIMARY KEY,
  remittance_id VARCHAR(128) NOT NULL UNIQUE,
  case_id VARCHAR(128),
  submission_id VARCHAR(128),
  external_ref VARCHAR(256),
  adjudication_status VARCHAR(32),
  paid_amount FLOAT,
  allowed_amount FLOAT,
  denial_codes JSON,
  payer_claim_id VARCHAR(128),
  source_format VARCHAR(32),
  raw_payload JSON,
  timestamp_utc VARCHAR(64)
);

CREATE TABLE IF NOT EXISTS payment_postings (
  id INTEGER PRIMARY KEY,
  payment_post_id VARCHAR(128) NOT NULL UNIQUE,
  case_id VARCHAR(128) NOT NULL,
  remittance_id VARCHAR(128),
  rail VARCHAR(32) NOT NULL,
  amount FLOAT,
  currency VARCHAR(8),
  idempotency_key VARCHAR(128) NOT NULL,
  external_ref VARCHAR(256),
  status VARCHAR(32),
  raw_payload JSON,
  posted_at VARCHAR(64),
  UNIQUE(case_id, idempotency_key)
);

CREATE TABLE IF NOT EXISTS playbooks (
  id INTEGER PRIMARY KEY,
  payer_id VARCHAR(64) NOT NULL,
  procedure_code VARCHAR(64) NOT NULL,
  payload JSON NOT NULL,
  updated_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS audit_events (
  id INTEGER PRIMARY KEY,
  event_type VARCHAR(64) NOT NULL,
  actor_id VARCHAR(128) NOT NULL,
  resource_type VARCHAR(64) NOT NULL,
  resource_id VARCHAR(128) NOT NULL,
  outcome VARCHAR(64),
  details JSON,
  trace_id VARCHAR(64),
  timestamp_utc VARCHAR(64)
);

CREATE TABLE IF NOT EXISTS kpi_snapshots (
  id INTEGER PRIMARY KEY,
  scope VARCHAR(64),
  payload JSON NOT NULL,
  created_at TIMESTAMP
);
