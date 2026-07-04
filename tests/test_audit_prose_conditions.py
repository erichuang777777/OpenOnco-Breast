"""Phase 1 triage tool — unit tests.

Module: scripts/audit_prose_conditions.py
Context: docs/reviews/fable-opinion.md Section 5, Phase 1. This is a
best-effort triage aid over the 654 prose conditions found by
scripts/check_prose_conditions.py — classifying each by structural
impact (does fixing it change routing?) and confidence (how mappable
is the prose onto a real finding key?). Never authoritative; every row
still needs human review before landing in a real Algorithm YAML.

Two real bugs were caught and fixed while building this against the
actual corpus (not synthetic examples) — both are regression-tested
here:
  1. A segment naming multiple genes ("TET2/DNMT3A/IDH2") was falsely
     "resolved" by a single-gene candidate (idh2_status) that only
     covers one of the three.
  2. The fix for (1) then falsely blocked a *correct* match ("ECOG
     PS 0-1" -> ecog_status) because it treated any 2+ all-caps
     tokens as "multiple genes" — including non-gene abbreviation
     pairs like ECOG/PS. Narrowed to only trigger on an explicit
     slash/comma-separated list.
"""

from __future__ import annotations

from scripts.audit_prose_conditions import (
    _best_match,
    _clause_is_working,
    _explicit_gene_list_tokens,
    _gene_like_tokens,
    _split_segments,
    _tokenize,
    classify_confidence,
    _classify_structural,
)


# ── Tokenization / segment splitting ─────────────────────────────────────


def test_tokenize_strips_stopwords_and_short_tokens():
    tokens = _tokenize("HCV RNA positive")
    assert tokens == {"hcv", "rna"}


def test_split_segments_on_and():
    segments = _split_segments("HCV RNA positive AND indolent presentation")
    assert segments == ["HCV RNA positive", "indolent presentation"]


def test_split_segments_on_or_case_insensitive():
    segments = _split_segments("HCV RNA negative or no antiviral candidate")
    assert segments == ["HCV RNA negative", "no antiviral candidate"]


def test_split_segments_no_connective_returns_single_segment():
    assert _split_segments("ECOG PS 0-1") == ["ECOG PS 0-1"]


# ── Gene-token detection ─────────────────────────────────────────────────


def test_gene_like_tokens_finds_all_caps():
    """This broader detector deliberately over-includes (e.g. "AITL" is
    a disease-subtype acronym, not a gene) — it's only a rough signal
    for "does this segment look like it names something specific."
    The narrower `_explicit_gene_list_tokens` (tested below) is what
    the multi-gene safeguard actually relies on."""
    tokens = _gene_like_tokens("AITL-typical epigenetic mutations (TET2/DNMT3A/IDH2)")
    assert tokens == ["AITL", "TET2", "DNMT3A", "IDH2"]


def test_explicit_gene_list_requires_slash_or_comma_separator():
    """The narrower detector used for the multi-gene safeguard must not
    fire on a loose abbreviation pair like 'ECOG PS' (regression test
    for the false-negative this caused)."""
    assert _explicit_gene_list_tokens("ECOG PS 0-1") == []
    assert _explicit_gene_list_tokens("TET2/DNMT3A/IDH2") == ["TET2", "DNMT3A", "IDH2"]
    assert _explicit_gene_list_tokens("BRCA1, BRCA2 germline") == ["BRCA1", "BRCA2"]


# ── Matching (with coverage-ratio + multi-gene safeguards) ───────────────


def test_best_match_finds_exact_subset():
    registry = {"hcv_rna": {"hcv", "rna"}}
    assert _best_match(_tokenize("HCV RNA positive"), registry) == "hcv_rna"


def test_best_match_rejects_low_coverage_ratio():
    """A single-token candidate buried in a long, multi-concept segment
    must not count as a resolution (regression test for the histology
    false-positive found against the real corpus)."""
    registry = {"b_symptoms_present": {"b", "symptoms"}}
    segment = (
        "Aggressive histology suspected at relapse (rapid growth, "
        "B-symptoms, LDH raised, extranodal sites)"
    )
    assert _best_match(_tokenize(segment), registry) is None


def test_best_match_accepts_high_coverage_ratio():
    registry = {"peripheral_neuropathy_grade": {"peripheral", "neuropathy", "grade"}}
    segment = "No severe peripheral neuropathy (Grade >=2)"
    assert _best_match(_tokenize(segment), registry) == "peripheral_neuropathy_grade"


def test_best_match_does_not_match_variant_specific_candidate_to_generic_gene_mention():
    """A generic "IDH2" mention must not match a variant-specific
    candidate whose tokens (e.g. "r140q") aren't actually present."""
    registry = {"bio_idh2_r140q": {"idh2", "r140q"}}
    assert _best_match(_tokenize("IDH2 mutation documented"), registry) is None


def test_classify_confidence_multi_gene_list_needs_new_finding():
    """Regression test: TET2/DNMT3A/IDH2 must not be falsely resolved
    by a single idh2-only candidate."""
    registry = {"idh2_status": {"idh2"}}
    confidence, matches = classify_confidence(
        "AITL-typical epigenetic mutations documented (TET2/DNMT3A/IDH2)",
        registry,
    )
    assert confidence == "NEEDS_NEW_FINDING"
    assert matches == []


def test_classify_confidence_ecog_ps_still_resolves():
    """Regression test: the multi-gene safeguard must not block this
    legitimate two-abbreviation, single-concept match."""
    registry = {"ecog_status": {"ecog"}}
    confidence, matches = classify_confidence("ECOG PS 0-1", registry)
    assert confidence == "HIGH_CONFIDENCE_RENAME"
    assert matches == ["ecog_status"]


def test_classify_confidence_all_segments_resolved_is_high_confidence():
    registry = {"brca1_status": {"brca1"}, "brca2_status": {"brca2"}}
    confidence, matches = classify_confidence(
        "BRCA1 positive AND BRCA2 positive", registry
    )
    assert confidence == "HIGH_CONFIDENCE_RENAME"
    assert set(matches) == {"brca1_status", "brca2_status"}


def test_classify_confidence_vague_prose_needs_clinical_judgment():
    registry: dict[str, set[str]] = {}
    confidence, matches = classify_confidence(
        "Significant comorbidity burden", registry
    )
    assert confidence == "NEEDS_CLINICAL_JUDGMENT"
    assert matches == []


def test_classify_confidence_unmatched_gene_needs_new_finding():
    registry: dict[str, set[str]] = {}
    confidence, matches = classify_confidence(
        "KRAS G12C mutation confirmed", registry
    )
    assert confidence == "NEEDS_NEW_FINDING"


# ── Structural classification ────────────────────────────────────────────


def test_structural_any_of_with_working_sibling_is_dead():
    assert _classify_structural("any_of", has_working_sibling=True) == "DEAD"


def test_structural_any_of_without_working_sibling_is_sole_any():
    assert _classify_structural("any_of", has_working_sibling=False) == "SOLE_ANY"


def test_structural_all_of_without_working_sibling_is_sole_all():
    assert _classify_structural("all_of", has_working_sibling=False) == "SOLE_ALL"


def test_structural_all_of_with_working_sibling_is_still_mixed_all_not_dead():
    """An AND with one broken clause is just as broken as an AND with
    all clauses broken — the working sibling doesn't save it."""
    assert _classify_structural("all_of", has_working_sibling=True) == "MIXED_ALL"


def test_clause_is_working_for_finding_and_red_flag():
    def is_prose(text):
        return " " in text  # simple stand-in for this unit test

    assert _clause_is_working({"finding": "ecog"}, is_prose) is True
    assert _clause_is_working({"red_flag": "RF-X"}, is_prose) is True
    assert _clause_is_working({"condition": "BIO-EGFR-MUT"}, is_prose) is True
    assert _clause_is_working({"condition": "some prose here"}, is_prose) is False


# ── End-to-end sanity check against the real corpus ──────────────────────


def test_audit_runs_against_real_corpus_and_totals_match_ratchet_baseline():
    """The Phase 1 tool's total prose-condition count must match Phase
    0's simpler ratchet count exactly — same underlying detector, same
    corpus, counted two different ways. A mismatch would mean the two
    tools have drifted out of sync with each other."""
    from scripts.audit_prose_conditions import audit_algorithms
    from scripts.check_prose_conditions import count_conditions

    audit_rows = audit_algorithms()
    ratchet_counts = count_conditions()

    assert len(audit_rows) == sum(c["prose"] for c in ratchet_counts.values())

    # Every row must have a valid structural class and confidence tier.
    valid_structural = {"DEAD", "SOLE_ANY", "SOLE_ALL", "MIXED_ALL"}
    valid_confidence = {
        "HIGH_CONFIDENCE_RENAME", "NEEDS_NEW_FINDING", "NEEDS_CLINICAL_JUDGMENT",
    }
    for row in audit_rows:
        assert row["structural_class"] in valid_structural
        assert row["confidence"] in valid_confidence
