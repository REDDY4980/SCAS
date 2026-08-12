"""
Explanation Engine.

AIB v1.0 Vol 10.9: each recommendation must include crop name,
confidence %, suitable soil characteristics, supporting climate
factors, key nutrients influencing the decision, rule-based
observations.
"""

from __future__ import annotations

from app.rules.confidence_engine import ScoredCrop

# Vol 9.13 top contributing feature names, human-readable.
_FEATURE_LABELS = {
    "N": "nitrogen level",
    "P": "phosphorus level",
    "K": "potassium level",
    "temperature": "temperature",
    "humidity": "humidity",
    "ph": "soil pH",
    "rainfall": "rainfall",
}


def _top_contributing_features(feature_importance: dict[str, float], n: int = 3) -> list[str]:
    ranked = sorted(feature_importance.items(), key=lambda kv: kv[1], reverse=True)
    return [_FEATURE_LABELS.get(name, name) for name, _ in ranked[:n]]


def build_explanation(
    scored: ScoredCrop,
    soil: dict[str, float | None],
    weather: dict[str, float | None] | None,
    feature_importance: dict[str, float],
) -> str:
    """Vol 10.9 human-readable explanation for a single crop recommendation."""
    parts: list[str] = []

    top_features = _top_contributing_features(feature_importance)
    parts.append(
        f"The model's Top-3 most influential factors overall are "
        f"{', '.join(top_features)}."
    )

    ph = soil.get("ph")
    if ph is not None:
        parts.append(f"This farm's soil pH is {ph:.2f}.")

    if weather:
        temp = weather.get("temperature")
        rainfall = weather.get("rainfall")
        if temp is not None and rainfall is not None:
            parts.append(
                f"Current conditions show a temperature of {temp:.1f}°C and "
                f"rainfall of {rainfall:.1f}mm, which were factored into this prediction."
            )

    rule_texts = [n.explanation for n in scored.rule_evaluation.notes if n.effect != "info"]
    if rule_texts:
        parts.append("Agronomic validation: " + " ".join(rule_texts))

    info_texts = [n.explanation for n in scored.rule_evaluation.notes if n.effect == "info"]
    if info_texts:
        parts.append(" ".join(info_texts))

    return " ".join(parts)
