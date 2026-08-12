"""Fertilizer knowledge base tests — against the real Requirement 2 KB."""

from app.rules.fertilizer_knowledge_base import FertilizerKnowledgeBase


def test_loads_real_kb_products():
    kb = FertilizerKnowledgeBase()
    urea = kb.get_product("Urea")
    assert urea is not None
    assert urea.n_percent == 46.0
    assert urea.grade == "46-0-0"


def test_loads_real_kb_case_insensitive():
    kb = FertilizerKnowledgeBase()
    assert kb.get_product("urea") is not None
    assert kb.get_product("UREA") is not None


def test_maize_matches_exactly():
    kb = FertilizerKnowledgeBase()
    dose = kb.lookup_crop("maize")
    assert dose is not None
    assert dose.n_kg_ha == 150
    assert dose.p2o5_kg_ha == 75
    assert dose.k2o_kg_ha == 40


def test_rice_does_not_fuzzy_match_hybrid_paddy():
    """Critical safety property: 'rice' (ML label) must NOT silently
    match 'Hybrid Paddy' (a specific documented variety) — that would
    misrepresent sourced evidence as applying to a crop it never
    validated."""
    kb = FertilizerKnowledgeBase()
    assert kb.lookup_crop("rice") is None


def test_unknown_crop_returns_none():
    kb = FertilizerKnowledgeBase()
    assert kb.lookup_crop("dragonfruit") is None


def test_unknown_product_returns_none():
    kb = FertilizerKnowledgeBase()
    assert kb.get_product("Nonexistent Fertilizer") is None
