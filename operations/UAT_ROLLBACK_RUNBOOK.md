# UAT and Rollback Runbook

## Live UAT (No Mocks)
1. Ensure deployment is running with live connector credentials.
2. Generate or obtain a signed JWT for UAT actor (`admin`, `ops_submitter`, `reviewer`, `viewer` as needed).
3. Run UAT flow for US:
   - `python scripts/run_live_uat.py --base-url https://<api-host> --token <jwt> --dataset us --out artifacts/live_uat_us.json`
4. Run UAT flow for India:
   - `python scripts/run_live_uat.py --base-url https://<api-host> --token <jwt> --dataset in --out artifacts/live_uat_in.json`
5. Verify both reports have `"ok": true`.

## Rollback Drill
1. Backup primary DB:
   - `python scripts/db_backup.py --database-url postgresql+psycopg://... --out backups/pre_release.dump`
2. Restore to validation DB:
   - `python scripts/db_restore.py --database-url postgresql+psycopg://... --in backups/pre_release.dump --clean`
3. Validate schema:
   - `DATABASE_URL=postgresql+psycopg://... python scripts/db_readiness.py`
4. Optional one-shot drill:
   - `python scripts/run_rollback_drill.py --primary-db-url postgresql+psycopg://... --backup-out backups/drill.dump --restore-db-url postgresql+psycopg://... --clean-restore --report-out artifacts/rollback_drill_report.json`

## Incident Rollback Decision
- Roll app only if issue is stateless or backward compatible with current schema.
- Roll DB from backup only when data corruption or irreversible schema issue is confirmed.
- Always restore to validation DB first, then swap traffic after smoke pass.
