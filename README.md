# Claims Triage Engine

A rule-based triage engine for regulated review workflows where decisions need to be explainable, not just accurate.

Every decision the engine produces — approve, reject, pend-for-review, or abstain — is traceable back to the specific inputs, rule, and actor involved. This makes it suitable for domains where "the model said so" is not good enough: insurance, healthcare authorisation, compliance, and similar. The engine is deliberately not a black-box classifier.

Adapted here as a healthcare prior-authorisation simulator covering US X12 278/837-style and India pre-authorisation flows, with simulated payer connector logic, acknowledgement polling, and outcome closure.

## Stack
Python · FastAPI · PostgreSQL · Docker

## Run locally

```bash
git clone https://github.com/dexflex66/claims-triage-engine
cd claims-triage-engine
docker compose up
```

43 automated tests cover decision logic, workflow handling, connector flows, audit trail, and failure modes.