PYTHON ?= /Library/Frameworks/Python.framework/Versions/3.10/bin/python3
ENV_FLAGS = OIDC_REQUIRE_SIGNATURE=false KEY_ROTATION_ENFORCED=false MTLS_REQUIRED=false IP_ALLOWLIST_ENABLED=false

.PHONY: help test-all smoke-us smoke-in smoke-all shadow-replay docker-build docker-up docker-down db-migrate db-readiness

help:
	@echo "Targets:"
	@echo "  make test-all   - Run full pytest suite with safe local flags"
	@echo "  make smoke-us   - Run end-to-end US smoke flow and save summary JSON"
	@echo "  make smoke-in   - Run end-to-end IN smoke flow and save summary JSON"
	@echo "  make smoke-all  - Run both US and IN smoke flows"
	@echo "  make shadow-replay - Replay fixture historical cases through no-spend flow"
	@echo "  make docker-build - Build container image"
	@echo "  make docker-up - Start app+postgres via docker compose"
	@echo "  make docker-down - Stop docker compose stack"
	@echo "  make db-migrate - Apply SQL migrations in db/migrations"
	@echo "  make db-readiness - Check migration and DB connectivity readiness"
	@echo ""
	@echo "Override interpreter if needed:"
	@echo "  make PYTHON=python3 test-all"

test-all:
	@$(ENV_FLAGS) $(PYTHON) -m pytest -q

smoke-us:
	@mkdir -p artifacts
	@$(ENV_FLAGS) $(PYTHON) scripts/staging_smoke.py --dataset us --output artifacts/staging_smoke_us.json
	@echo "Wrote artifacts/staging_smoke_us.json"

smoke-in:
	@mkdir -p artifacts
	@$(ENV_FLAGS) $(PYTHON) scripts/staging_smoke.py --dataset in --output artifacts/staging_smoke_in.json
	@echo "Wrote artifacts/staging_smoke_in.json"

smoke-all: smoke-us smoke-in
	@echo "Wrote artifacts/staging_smoke_us.json and artifacts/staging_smoke_in.json"

shadow-replay:
	@mkdir -p artifacts
	@$(ENV_FLAGS) $(PYTHON) scripts/shadow_replay.py \
		--input fixtures/shadow/historical_cases.jsonl \
		--output-csv artifacts/shadow_replay_rows.csv \
		--output-summary artifacts/shadow_replay_summary.json
	@echo "Wrote artifacts/shadow_replay_rows.csv and artifacts/shadow_replay_summary.json"

docker-build:
	@docker build -t payer-proof-claims:local .

docker-up:
	@docker compose up --build -d

docker-down:
	@docker compose down

db-migrate:
	@$(PYTHON) scripts/apply_migrations.py

db-readiness:
	@$(PYTHON) scripts/db_readiness.py
