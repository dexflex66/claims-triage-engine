# Payer-Proof Claims — Scope: General Radiology Prior Authorization

## Wedge

- **Specialty:** General radiology (prior authorization).
- **Markets:** US and India (parallel-light).
- **Buyer:** Mid-market clinic operations and prior-auth staff.

## Code Sets

### Top 25 general radiology codes (CPT / equivalent)

US (CPT):

- 70450, 70460, 70470, 70480, 70486, 70490, 70551, 70552, 70553, 71250, 71260, 71270, 72148, 72149, 73718, 73719, 73720, 73721, 74176, 74177, 74178, 76700, 76705, 76770, 77080

India (common radiology procedure codes / local equivalents for prior auth):

- Aligned to same clinical basket: head CT, chest X-ray, spine MRI, extremity MRI, abdominal CT, ultrasound abdomen, etc. (same 25 procedures, local code strings in `claims_policy_india.yaml`).

## Payers

### US (2)

1. **BCBS** (Blue Cross Blue Shield) — representative prior-auth criteria.
2. **Aetna** — representative prior-auth criteria.

### India (2)

1. **Star Health** — representative prior-auth / pre-authorization criteria.
2. **HDFC ERGO Health** — representative prior-auth / pre-authorization criteria.

## Out of scope for MVP

- Other specialties (e.g., cardiology, oncology).
- Additional payers beyond the two per country.
- Full EMR/EHR integration (manual upload / export only for MVP).
