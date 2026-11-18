"""
Realistic OCR-line fixtures drawn from the actual redacted Soil Health
Card samples in Requirement 4 (SOURCE_REGISTER: SHC-KA-2017,
SHC-TASAR-2017). These are the real analytical values from those cards,
reformatted as the layout-reconstructed text lines the OCR pipeline's
Layout Analysis stage would hand to the field parser (AIB Vol 7.3).

Using real calibration data here (rather than synthetic numbers) is the
entire point of Requirement 4 per OCR_CALIBRATION_NOTES.md: "calibrate
OCR against actual filled farmer-specific reports."
"""

# SHC-KA-2017 — Karnataka Government SHC, Soil Health Centre Bagalkote
# (PSSCIVE/NCERT Grade 12 textbook reproduction, pages 76-79).
KARNATAKA_SHC_LINES = [
    "Soil Health Centre, Bagalkote",
    "Soil Type: Black Soil",
    "Date of Sample Collection 10/09/2017",
    "Farm Size, Irrigation Status 2.16 Acre Irrigated (Bore well)",
    "1 pH 7.70 Moderately alkaline 7, Neutral",
    "2 EC 0.04 dS/m Normal 0-1 dS/m",
    "3 Organic Carbon (OC) 0.35 % Low 0.51-0.75%",
    "4 Available Nitrogen (N) 200.6 kg/ha Low 280-560 kg/ha",
    "5 Available Phosphorus (P) 4.19 kg/ha Very Low 23-57 kg/ha",
    "6 Available Potassium (K) 122.8 kg/ha Low 145-337 kg/ha",
    "7 Available Sulphur (S) 26.50 ppm Sufficient > 10 ppm",
    "8 Available Zinc (Zn) 0.27 ppm Deficient > 0.6 ppm",
    "9 Available Boron (B) 0.63 ppm Sufficient > 0.5 ppm",
    "10 Available Iron (Fe) 0.71 ppm Deficient > 4.5 ppm",
    "11 Available Manganese (Mn) 6.41 ppm Sufficient > 2.0 ppm",
    "12 Available Copper (Cu) 1.65 ppm Sufficient > 0.2 ppm",
]

KARNATAKA_SHC_EXPECTED = {
    "ph": 7.70,
    "ec": 0.04,
    "organic_carbon": 0.35,
    "nitrogen": 200.6,
    "phosphorus": 4.19,
    "potassium": 122.8,
    "sulphur": 26.50,
    "zinc": 0.27,
    "boron": 0.63,
    "iron": 0.71,
    "manganese": 6.41,
    "copper": 1.65,
}

# SHC-TASAR-2017 sample #1 — Central Tasar Research and Training
# Institute, Central Silk Board (Ranchi), filled card 1.
TASAR_SHC_SAMPLE_1_LINES = [
    "CENTRAL TASAR RESEARCH AND TRAINING INSTITUTE, RANCHI",
    "1 pH 6.37 Acidic",
    "2 EC 0.094 dS m-1 Good",
    "3 Organic Carbon (OC) 0.57 % Medium",
    "4 Available Nitrogen (N) 111.7 kg ha-1 Low",
    "5 Available Phosphorus (P) 9.30 kg ha-1 Low",
    "6 Available Potassium (K) 180.3 kg ha-1 Medium",
    "7 Available Sulphur (S) 5.15 ppm Low",
    "8 Available Zinc (Zn) 0.18 ppm Deficient",
    "9 Available Boron (B) 3.14 ppm Sufficient",
    "10 Available Iron (Fe) 18.90 ppm Sufficient",
    "11 Available Manganese (Mn) 1.80 ppm Deficient",
    "12 Available Copper (Cu) 0.84 ppm Sufficient",
]

TASAR_SHC_SAMPLE_1_EXPECTED = {
    "ph": 6.37,
    "ec": 0.094,
    "organic_carbon": 0.57,
    "nitrogen": 111.7,
    "phosphorus": 9.30,
    "potassium": 180.3,
    "sulphur": 5.15,
    "zinc": 0.18,
    "boron": 3.14,
    "iron": 18.90,
    "manganese": 1.80,
    "copper": 0.84,
}

# SHC-TASAR-2017 sample #4 — a card with very deficient Cu (0.09), the
# tightest edge case in the calibration set, useful for range-boundary
# testing.
TASAR_SHC_SAMPLE_4_LINES = [
    "CENTRAL TASAR RESEARCH AND TRAINING INSTITUTE, RANCHI",
    "1 pH 5.28 Acidic",
    "2 EC 0.063 dS m-1 Good",
    "3 Organic Carbon (OC) 0.33 % Low",
    "4 Available Nitrogen (N) 126.8 kg ha-1 Low",
    "5 Available Phosphorus (P) 4.80 kg ha-1 Low",
    "6 Available Potassium (K) 123.2 kg ha-1 Medium",
    "7 Available Sulphur (S) 6.90 ppm Low",
    "8 Available Zinc (Zn) 0.44 ppm Deficient",
    "9 Available Boron (B) 6.11 ppm Sufficient",
    "10 Available Iron (Fe) 12.50 ppm Sufficient",
    "11 Available Manganese (Mn) 13.50 ppm Sufficient",
    "12 Available Copper (Cu) 0.09 ppm Deficient",
]

TASAR_SHC_SAMPLE_4_EXPECTED = {
    "ph": 5.28,
    "ec": 0.063,
    "organic_carbon": 0.33,
    "nitrogen": 126.8,
    "phosphorus": 4.80,
    "potassium": 123.2,
    "sulphur": 6.90,
    "zinc": 0.44,
    "boron": 6.11,
    "iron": 12.50,
    "manganese": 13.50,
    "copper": 0.09,
}

# SHC-TASAR-2017 samples #2 and #3 — transcribed by hand from the rendered
# pages of datasets/ocr_calibration/02_Central_Tasar_SHCs_redacted_2017.pdf
# (pages 2 and 3), independently of any OCR output.
TASAR_SHC_SAMPLE_2_EXPECTED = {
    "ph": 6.32,
    "ec": 0.096,
    "organic_carbon": 0.48,
    "nitrogen": 123.0,
    "phosphorus": 3.30,
    "potassium": 203.8,
    "sulphur": 6.68,
    "zinc": 0.27,
    "boron": 9.34,
    "iron": 19.00,
    "manganese": 7.65,
    "copper": 0.28,
}

TASAR_SHC_SAMPLE_3_EXPECTED = {
    "ph": 5.23,
    "ec": 0.046,
    "organic_carbon": 0.33,
    "nitrogen": 120.5,
    "phosphorus": 14.20,
    "potassium": 191.5,
    "sulphur": 4.50,
    "zinc": 0.37,
    "boron": 1.43,
    "iron": 15.70,
    "manganese": 6.30,
    "copper": 0.26,
}

# Page-by-page ground truth for the Tasar PDF (one farmer card per page).
TASAR_SHC_PAGES_EXPECTED = [
    TASAR_SHC_SAMPLE_1_EXPECTED,
    TASAR_SHC_SAMPLE_2_EXPECTED,
    TASAR_SHC_SAMPLE_3_EXPECTED,
    TASAR_SHC_SAMPLE_4_EXPECTED,
]
