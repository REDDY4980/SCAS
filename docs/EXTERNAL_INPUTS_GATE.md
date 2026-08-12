# SCAS — External Inputs / Upload Gate

## Included in this ZIP

All four data/domain requirements identified in the Claude kickoff B.2 are included:

1. Crop recommendation dataset
2. Fertilizer knowledge base
3. Agronomic rule set
4. Real filled farmer soil reports for OCR calibration

The original Claude kickoff package is also included.

## Important: AIB Volumes 1–19

The kickoff document says AIB v1.0 (Volumes 1–19) is the single source of truth.

The current master ZIP includes the **kickoff package that references and summarizes those volumes**, but it does NOT invent or recreate the unseen AIB volumes.

If Claude/OpenHands does not already have the complete AIB Volumes 1–19, those original project documents must also be uploaded before implementation. Do not replace them with generated summaries.

## Not included intentionally

No real secrets are included:
- OpenWeatherMap API key
- PostgreSQL production password
- cloud credentials
- domain/DNS credentials
- Docker registry credentials
- GitHub personal access token

Use `.env.example` and secret storage.

## Optional later inputs

- Actual SCAS GitHub repository URL
- production cloud target
- domain
- Play Console account
- proprietary/field crop dataset, if later available
