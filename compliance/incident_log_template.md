# Incident log template (HIPAA / security)

Use one row per incident. Do not store PHI in this log.

| Date (UTC) | Incident ID | Type | Description | Affected resources | Action taken | Closed (Y/N) |
|------------|-------------|------|-------------|--------------------|--------------|--------------|
| YYYY-MM-DD | INC-001     | e.g. unauthorized_access, breach, misconfig | Short description | case_id / user_id (no PHI) | Mitigation steps | N |

- Type: unauthorized_access | data_breach | misconfiguration | availability | other
- Store incident log in a restricted, append-only location; restrict access to admin + audit:read.
