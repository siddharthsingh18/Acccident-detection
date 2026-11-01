# Argus Batch Evaluation & Verification Report

- **Total Clips Evaluated**: 463
- **Generated At**: 2026-11-01 18:49:17 UTC
- **CSV Artifact**: `artifacts/batch_results.csv`

## Categorization Breakdown

| Category | Description | Count |
|---|---|---|
| **Category A** | Unplayable / Corrupt files | 0 |
| **Category B** | Short (<30 frame) clips padded & processed | 331 |
| **Category C** | Historical camera ID collision isolated (no false alarms) | 0 |
| **Category D** | Unlabeled / Ambiguous clips | 2 |
| **Category E** | Verified Working (Accident alert & Normal flow) | 130 |

## Evaluation Outcomes

| Outcome State | Count | Percentage |
|---|---|---|
| Alert on accident clip | 336 | 72.6% |
| No alert on normal clip | 125 | 27.0% |
| Missed accident | 0 | 0.0% |
| False alarm | 0 | 0.0% |
| Not scored (unlabeled) | 2 | 0.4% |
