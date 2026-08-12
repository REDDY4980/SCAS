"""
Agronomic Rule Engine.

AIB v1.0 Vol 10.6: "Validate ML predictions against agricultural
constraints... Reject crops violating hard agronomic constraints.
Penalize crops violating soft constraints."

This engine is a *thin evaluator* over the actual source-traceable rule
set supplied in Requirement 3 (`agronomic_rules_v1.json`) — it does not
invent thresholds. Its own `unknown_rule_policy` is honored exactly:

    "when_no_authoritative_rule_exists": "do_not_hard_reject"
    "effect": "apply_uncertainty_penalty_to_rule_score"

Coverage note (honest limitation, not silently ignored): the real rule
set includes `regional_context` rules keyed on
`state == Karnataka AND agroclimatic_zone == 5`. The `farms` table
(Vol 5.3) has no `agroclimatic_zone` column, so those specific rules
structurally cannot fire yet — they are loaded and reported as
"insufficient context" rather than guessed at using state alone, per
the rule set's own "do_not_hard_reject... unknown evidence must not be
treated as a violation" principle applied to missing *inputs*, not just
missing *rules*.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger("scas.rules.agronomic")

_DEFAULT_RULES_PATH = (
    Path(__file__).resolve().parents[3] / "datasets" / "agronomic_rules" / "agronomic_rules_v1.json"
)
# `parents[3]` assumes this file sits three directories below the repo
# root (backend/app/rules/agronomic_rules.py -> repo root), which is
# true for local/test runs but not inside the Docker image — there,
# `COPY . .` puts backend's contents directly at /app, so this file is
# only two directories below /app and the same traversal overshoots to
# filesystem root. Settings.agronomic_rules_path (unset locally, set
# explicitly in docker-compose.yml) is checked first so Docker can
# supply the correct bind-mounted path without disturbing the
# already-correct local/test resolution above.

# Vol 10.7 confidence adjustment magnitudes. These weights are SCAS
# engineering decisions (not values sourced from the rule set — the
# rule set gives directionality and conditions, not exact score deltas),
# chosen conservatively per the evidence hierarchy's own instruction
# that a "preferred range" should adjust confidence, not gate it.
_POSITIVE_BONUS = 0.05
_WARNING_PENALTY = 0.05
_SOIL_STATUS_PENALTY_PER_FLAG = 0.02
_SOIL_STATUS_PENALTY_CAP = 0.08
_UNKNOWN_CROP_RULE_PENALTY = 0.01

_KARNATAKA_ZONE5_CROPS = {
    "ragi", "groundnut", "pigeon pea", "pigeonpeas", "cowpea", "horse gram", "field bean", "millets"
}


@dataclass
class RuleNote:
    rule_id: str
    effect: str  # "bonus" | "penalty" | "info"
    magnitude: float
    explanation: str


@dataclass
class RuleEvaluation:
    crop: str
    score_adjustment: float  # signed; added directly to model confidence
    notes: list[RuleNote] = field(default_factory=list)
    soil_status_flags: dict[str, bool] = field(default_factory=dict)


class AgronomicRuleEngine:
    """Vol 10.16 suggested module: rules/agronomic_rules.py."""

    def __init__(self, rules_path: str | Path | None = None):
        if rules_path is None:
            from app.core.config import get_settings

            rules_path = get_settings().agronomic_rules_path or _DEFAULT_RULES_PATH
        self.rules_path = Path(rules_path)
        self._ruleset = json.loads(self.rules_path.read_text())
        self._rules_by_id = {r["id"]: r for r in self._ruleset["rules"]}

    def _classify_soil_status(self, soil: dict[str, float | None]) -> dict[str, bool]:
        """Vol 10.6 soil_status rules — SHC national reference classes
        (AGR-SOIL-N-LOW, AGR-SOIL-P-LOW, AGR-SOIL-K-LOW, AGR-SOIL-OC-LOW)."""
        flags: dict[str, bool] = {}
        n = soil.get("nitrogen")
        if n is not None:
            flags["low_nitrogen"] = n < 280
        p = soil.get("phosphorus")
        if p is not None:
            flags["low_phosphorus"] = p < 10
        k = soil.get("potassium")
        if k is not None:
            flags["low_potassium"] = k < 120
        oc = soil.get("organic_carbon")
        if oc is not None:
            flags["low_organic_carbon"] = oc < 0.5
        return flags

    def _evaluate_rice_ph_rule(self, crop: str, soil: dict[str, float | None]) -> RuleNote | None:
        """AGR-RICE-PH / AGR-RICE-PH-OUT — the only crop_suitability rule
        with authoritative source coverage in the current rule set."""
        if crop.lower() != "rice":
            return None
        ph = soil.get("ph")
        if ph is None:
            return None
        if 5.5 <= ph <= 6.5:
            rule = self._rules_by_id["AGR-RICE-PH"]
            return RuleNote("AGR-RICE-PH", "bonus", _POSITIVE_BONUS, rule["explanation"])
        rule = self._rules_by_id["AGR-RICE-PH-OUT"]
        return RuleNote("AGR-RICE-PH-OUT", "penalty", _WARNING_PENALTY, rule["explanation"])

    def _evaluate_karnataka_soil_context(
        self, state: str | None, soil_type: str | None
    ) -> RuleNote | None:
        """AGR-KA-RED-BLACK-NPK-ZN — informational only (the rule's own
        `action` is 'increase_attention_to_N_P_Zn_status', not a
        bonus/penalty per rule_scoring's defined vocabulary)."""
        if not state or not soil_type:
            return None
        if state.strip().lower() != "karnataka":
            return None
        # Real farm data uses phrases like "Black Soil" or "Red Sandy
        # Loam", not the bare "black"/"red" the rule condition names —
        # match by containment, not exact equality, or this rule would
        # never fire against genuine data (found via the real Karnataka
        # SHC sample, which reports "Soil Type: Black Soil").
        soil_type_lower = soil_type.strip().lower()
        if "black" not in soil_type_lower and "red" not in soil_type_lower:
            return None
        rule = self._rules_by_id["AGR-KA-RED-BLACK-NPK-ZN"]
        return RuleNote(rule["id"], "info", 0.0, rule["explanation"])

    def evaluate(
        self,
        crop: str,
        soil: dict[str, float | None],
        farm_state: str | None = None,
        farm_soil_type: str | None = None,
    ) -> RuleEvaluation:
        notes: list[RuleNote] = []
        adjustment = 0.0

        soil_flags = self._classify_soil_status(soil)
        low_flag_count = sum(1 for v in soil_flags.values() if v)
        if low_flag_count > 0:
            penalty = min(low_flag_count * _SOIL_STATUS_PENALTY_PER_FLAG, _SOIL_STATUS_PENALTY_CAP)
            adjustment -= penalty
            flagged = [k.replace("low_", "") for k, v in soil_flags.items() if v]
            notes.append(
                RuleNote(
                    "AGR-SOIL-STATUS-COMPOSITE",
                    "penalty",
                    penalty,
                    f"Soil test indicates low {', '.join(flagged)} — SHC national reference "
                    f"classification (see datasets/agronomic_rules for source).",
                )
            )

        crop_rule_note = self._evaluate_rice_ph_rule(crop, soil)
        if crop_rule_note is not None:
            notes.append(crop_rule_note)
            adjustment += crop_rule_note.magnitude if crop_rule_note.effect == "bonus" else -crop_rule_note.magnitude
        else:
            # Vol 10 unknown_rule_policy: "do_not_hard_reject" +
            # "apply_uncertainty_penalty_to_rule_score" for crops with no
            # authoritative crop_suitability rule available yet.
            adjustment -= _UNKNOWN_CROP_RULE_PENALTY
            notes.append(
                RuleNote(
                    "AGR-UNKNOWN-CROP-RULE",
                    "info",
                    _UNKNOWN_CROP_RULE_PENALTY,
                    "Agronomic validation is limited for this crop; recommendation relies "
                    "primarily on the trained model. Add a reviewed crop-specific rule to "
                    "improve confidence calibration.",
                )
            )

        soil_context_note = self._evaluate_karnataka_soil_context(farm_state, farm_soil_type)
        if soil_context_note is not None:
            notes.append(soil_context_note)

        if farm_state and farm_state.strip().lower() == "karnataka" and crop.lower() in _KARNATAKA_ZONE5_CROPS:
            notes.append(
                RuleNote(
                    "AGR-KA-ZONE-5-CONTEXT-UNAVAILABLE",
                    "info",
                    0.0,
                    "This crop has a documented regional research context for Karnataka "
                    "Zone V, but the farm's agroclimatic zone is not recorded, so the "
                    "regional prior could not be applied.",
                )
            )

        return RuleEvaluation(crop=crop, score_adjustment=adjustment, notes=notes, soil_status_flags=soil_flags)
