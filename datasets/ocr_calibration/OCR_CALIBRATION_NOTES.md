# SCAS Requirement 4 — OCR Calibration Notes

## Why these samples were selected

The objective is to calibrate OCR against **actual filled farmer-specific reports**, not blank templates.

Included:
- a Karnataka Government Soil Health Card reproduced in a PSSCIVE/NCERT technical training publication;
- filled Soil Health Cards from the Central Tasar Research and Training Institute, Central Silk Board, Ministry of Textiles, Government of India;
- a recent 2025 East Godavari farmer report found publicly online, retained only as an external reference because it exposes personal identifiers.

## Privacy

The supplied PDFs are redacted copies. Farmer names, phone numbers, personal addresses, GPS coordinates and card-identifying numbers have been removed where applicable. Analytical values, labels, units, ratings, soil type, irrigation context, crop context and recommendation tables are retained.

## OCR fields to calibrate

Farmer/sample metadata:
- farmer_name
- father_name
- village
- taluk/mandal
- district
- state
- sample_id / SHC number
- collection date
- report date
- survey/khasra number
- farm area
- irrigation type
- soil type
- crop

Soil analytical fields:
- pH
- EC
- Organic Carbon (OC)
- Available Nitrogen (N)
- Available Phosphorus (P)
- Available Potassium (K)
- Sulphur (S)
- Zinc (Zn)
- Boron (B)
- Iron (Fe)
- Manganese (Mn)
- Copper (Cu)

Every extracted field should preserve:
1. raw OCR text
2. normalized field name
3. numeric value
4. unit
5. rating
6. confidence
7. page/bounding-box provenance
8. validation status

## Layout variation

The Karnataka and Central Silk Board reports intentionally expose different layouts, terminology, tables, headings and recommendation structures. This is useful for testing preprocessing, OCR, table extraction and field mapping.

## 2025 external example

A recent publicly indexed East Godavari report contains three samples for one farmer, received 15 January 2025 and completed 4 February 2025, with pH, EC, OC, N, P, K, S, B, Zn, Fe, Cu and Mn. It is recorded in SOURCE_REGISTER but not redistributed because the public copy contains direct personal identifiers.

## SCAS use

These files are OCR/input-format calibration resources. They are not ML crop-training data.

Pipeline:
upload → image/PDF preprocessing → OCR → table extraction → field normalization → validation → structured JSON → agronomic/ML layer.
