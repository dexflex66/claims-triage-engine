-- Performance indexes for production workloads
CREATE INDEX IF NOT EXISTS idx_case_evidence_case_id ON case_evidence(case_id);
CREATE INDEX IF NOT EXISTS idx_compile_results_case_id_created ON compile_results(case_id, id DESC);
CREATE INDEX IF NOT EXISTS idx_review_queue_case_status ON review_queue(case_id, status);
CREATE INDEX IF NOT EXISTS idx_review_actions_case_ts ON review_actions(case_id, timestamp_utc);
CREATE INDEX IF NOT EXISTS idx_submissions_case_status ON submissions(case_id, status);
CREATE INDEX IF NOT EXISTS idx_submissions_external_ref ON submissions(external_ref);
CREATE INDEX IF NOT EXISTS idx_submission_history_case_status ON submission_status_history(case_id, status);
CREATE INDEX IF NOT EXISTS idx_submission_history_extref_status ON submission_status_history(external_ref, status);
CREATE INDEX IF NOT EXISTS idx_reconciliation_events_case ON reconciliation_events(case_id);
CREATE INDEX IF NOT EXISTS idx_outcomes_case_outcome ON outcomes(case_id, outcome);
CREATE INDEX IF NOT EXISTS idx_remittances_case_status ON remittances(case_id, adjudication_status);
CREATE INDEX IF NOT EXISTS idx_payment_postings_case_status ON payment_postings(case_id, status);
CREATE INDEX IF NOT EXISTS idx_audit_events_trace_id ON audit_events(trace_id);
CREATE INDEX IF NOT EXISTS idx_audit_events_type_ts ON audit_events(event_type, timestamp_utc);
