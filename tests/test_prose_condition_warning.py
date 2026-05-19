"""Prose-condition warning surfaces silent-False free-text clauses.

Authors sometimes write `{condition: "ECOG PS 0-2"}` expecting predicate
evaluation, but `_eval_clause` only resolves flat finding keys, so the
clause silently returns False. The engine now logs a one-time WARNING
per unique prose string. Routing semantics are unchanged.

Audit: docs/reviews/openonco-state-audit-2026-05-17.md
"""

from __future__ import annotations

import logging

import pytest

from knowledge_base.engine import redflag_eval
from knowledge_base.engine.redflag_eval import _eval_clause


@pytest.fixture(autouse=True)
def _reset_warnings_cache():
    redflag_eval._reset_prose_warnings_for_tests()
    yield
    redflag_eval._reset_prose_warnings_for_tests()


def test_prose_condition_with_operator_warns_and_returns_false(caplog):
    with caplog.at_level(logging.WARNING, logger=redflag_eval.__name__):
        out = _eval_clause({"condition": "ECOG PS 0-2"}, {"ecog_ps": 1})
    assert out is False
    assert any(
        "prose_unevaluable" in r.getMessage() and "ECOG PS 0-2" in r.getMessage()
        for r in caplog.records
    ), caplog.records


def test_prose_condition_with_boolean_connective_warns(caplog):
    with caplog.at_level(logging.WARNING, logger=redflag_eval.__name__):
        out = _eval_clause(
            {"condition": "BRCA1 or BRCA2 somatic pathogenic variant"},
            {"biomarkers": {"BIO-BRCA1": "positive"}},
        )
    assert out is False
    assert any("BRCA1 or BRCA2" in r.getMessage() for r in caplog.records)


def test_flat_key_lookup_does_not_warn(caplog):
    """An ALL-CAPS finding key without operators is a legitimate flat
    lookup, not prose. No warning should fire even if the key is absent."""
    with caplog.at_level(logging.WARNING, logger=redflag_eval.__name__):
        out = _eval_clause({"condition": "BIO-BRCA1"}, {})
    assert out is False
    assert not [r for r in caplog.records if "prose_unevaluable" in r.getMessage()]


def test_truthy_finding_lookup_does_not_warn(caplog):
    """When the prose string happens to be a real finding key in patient
    data, the clause resolves to True and the warning is suppressed."""
    with caplog.at_level(logging.WARNING, logger=redflag_eval.__name__):
        out = _eval_clause(
            {"condition": "ECOG PS 0-2"},
            {"ECOG PS 0-2": True},  # author wired the key explicitly
        )
    assert out is True
    assert not [r for r in caplog.records if "prose_unevaluable" in r.getMessage()]


def test_warning_fires_once_per_unique_string(caplog):
    with caplog.at_level(logging.WARNING, logger=redflag_eval.__name__):
        for _ in range(5):
            _eval_clause({"condition": "ECOG PS 0-2"}, {})
    msgs = [r for r in caplog.records if "ECOG PS 0-2" in r.getMessage()]
    assert len(msgs) == 1


def test_structured_clause_unaffected(caplog):
    """Threshold / value forms keep their existing semantics — no warning
    even on miss, because the clause is structured."""
    with caplog.at_level(logging.WARNING, logger=redflag_eval.__name__):
        out = _eval_clause(
            {"finding": "ecog_ps", "threshold": 2, "comparator": "<="},
            {"ecog_ps": 1},
        )
    assert out is True
    assert not [r for r in caplog.records if "prose_unevaluable" in r.getMessage()]
