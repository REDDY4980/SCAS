"""
Fertilizer Knowledge Base loader.

AIB v1.0 Vol 11.7: "Maintain a configurable catalog... The knowledge
base shall be updateable without retraining the ML model."

Loads the real Requirement 2 starter KB (`fertilizer_knowledge_base_v1.json`).
Crop matching is deliberately EXACT (case-insensitive), never fuzzy —
the KB's own coverage_note states it "deliberately does not fabricate
fertilizer rules for all 22 ML crops," and guessing that the model's
"rice" prediction corresponds to the KB's "Hybrid Paddy" entry (a
specific hybrid variety with its own documented dose) would misrepresent
sourced evidence as applying to a crop it was never validated for.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

_DEFAULT_KB_PATH = (
    Path(__file__).resolve().parents[3]
    / "datasets"
    / "fertilizer_knowledge_base"
    / "fertilizer_knowledge_base_v1.json"
)
# See app/rules/agronomic_rules.py for why this repo-relative default
# doesn't resolve inside Docker (COPY . . flattens the directory depth
# this parents[3] traversal assumes) — Settings.fertilizer_kb_path is
# checked first so docker-compose.yml can supply the bind-mounted path.


@dataclass
class FertilizerProduct:
    name: str
    grade: str
    n_percent: float
    p2o5_percent: float
    k2o_percent: float
    primary_use: str
    source: str


@dataclass
class CropDoseRecommendation:
    crop: str
    region: str
    condition: str
    n_kg_ha: float
    p2o5_kg_ha: float
    k2o_kg_ha: float
    fertilizer_products: list[str]
    source: str
    source_url: str
    caution: str


class FertilizerKnowledgeBase:
    """Vol 11.14 suggested module: knowledge_base/fertilizers.json (loader)."""

    def __init__(self, kb_path: str | Path | None = None):
        if kb_path is None:
            from app.core.config import get_settings

            kb_path = get_settings().fertilizer_kb_path or _DEFAULT_KB_PATH
        self.kb_path = Path(kb_path)
        raw = json.loads(self.kb_path.read_text())

        self.products: dict[str, FertilizerProduct] = {}
        for f in raw["fertilizers"]:
            self.products[f["fertilizer"].lower()] = FertilizerProduct(
                name=f["fertilizer"],
                grade=f.get("grade", ""),
                n_percent=f.get("N_percent", 0.0) or 0.0,
                p2o5_percent=f.get("P2O5_percent", 0.0) or 0.0,
                k2o_percent=f.get("K2O_percent", 0.0) or 0.0,
                primary_use=f.get("primary_use", ""),
                source=f.get("source", ""),
            )

        self._crop_doses: dict[str, CropDoseRecommendation] = {}
        for c in raw["crop_recommendations"]:
            self._crop_doses[c["crop"].lower()] = CropDoseRecommendation(
                crop=c["crop"],
                region=c.get("region", ""),
                condition=c.get("condition", ""),
                n_kg_ha=c["N_kg_ha"],
                p2o5_kg_ha=c["P2O5_kg_ha"],
                k2o_kg_ha=c["K2O_kg_ha"],
                fertilizer_products=c.get("fertilizer_products", []),
                source=c.get("source", ""),
                source_url=c.get("source_url", ""),
                caution=c.get("caution", ""),
            )

        # Exact-match aliases only. "maize" (ML label) <-> "Maize" (KB
        # entry) is the sole direct correspondence in the current KB —
        # everything else in the KB names a specific variety/context
        # (e.g. "Hybrid Paddy") that the ML model's generic crop label
        # ("rice") does not confirm applies to.
        self._ml_label_aliases: dict[str, str] = {"maize": "maize"}

    def lookup_crop(self, ml_crop_label: str) -> CropDoseRecommendation | None:
        alias = self._ml_label_aliases.get(ml_crop_label.lower())
        if alias is None:
            return None
        return self._crop_doses.get(alias)

    def get_product(self, name: str) -> FertilizerProduct | None:
        return self.products.get(name.lower())
