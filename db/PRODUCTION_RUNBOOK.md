# Production DB Runbook

## Baseline
- Use PostgreSQL in production (`DATABASE_URL=postgresql+psycopg://...`).
- Keep SQLite only for local development and smoke tests.
- Apply SQL migrations from `/Users/mayank/Downloads/payer_proof_claims/db/migrations` before app rollout.

## Migration Workflow
1. Set `DATABASE_URL` to the production/staging Postgres URL.
2. Dry-run readiness:
   - `python scripts/db_readiness.py`
3. Apply pending migrations:
   - `python scripts/apply_migrations.py`
4. Re-check readiness:
   - `python scripts/db_readiness.py`

## Backup
- Create backup:
  - `python scripts/db_backup.py --out backups/payer_proof_claims_$(date +%Y%m%d_%H%M%S).dump`
- Backup format is `pg_dump --format=custom` for `pg_restore` compatibility.

## Restore Drill
1. Point `DATABASE_URL` to restore target DB.
2. Restore:
   - `python scripts/db_restore.py --in backups/<file>.dump --clean`
3. Validate:
   - `python scripts/db_readiness.py`
   - run API smoke (`make smoke-all`) against restored environment.

## Rollback Pattern
- For schema changes, prefer forward-only migrations.
- If app rollout fails:
  1. Roll app deployment back to previous image.
  2. Keep DB at latest schema unless data migration is backward-incompatible.
  3. If full rollback is required, restore from pre-deploy backup to an isolated DB and cut traffic only after validation.
