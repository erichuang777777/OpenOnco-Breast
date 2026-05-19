"""src_ctgov.yaml drift guard.

Gap 1 from docs/reviews/ctgov-wiring-audit-2026-05-18.md: the code
constant SRC-CTGOV-REGISTRY (referenced from ctgov_client, the
experimental_option schema, and mdt_orchestrator) must resolve to a
real Source entity. Validator only checks YAML-to-YAML refs, not code
constants — so this test closes the missing invariant.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from knowledge_base.clients.ctgov_client import CtgovClient
from knowledge_base.schemas import Source


_SRC_YAML = (
    Path(__file__).parent.parent
    / "knowledge_base"
    / "hosted"
    / "content"
    / "sources"
    / "src_ctgov.yaml"
)


def _load() -> Source:
    return Source.model_validate(yaml.safe_load(_SRC_YAML.read_text(encoding="utf-8")))


def test_src_ctgov_yaml_exists_and_loads():
    assert _SRC_YAML.is_file(), f"missing Source entity at {_SRC_YAML}"
    src = _load()
    assert src.id == "SRC-CTGOV-REGISTRY"


def test_source_id_matches_client_constant():
    """The whole point of this PR — code constant resolves to an entity."""
    src = _load()
    assert CtgovClient.source_id == src.id


def test_license_metadata_is_us_public_domain():
    src = _load()
    assert src.hosting_mode.value == "referenced"
    assert src.license is not None
    assert "Public Domain" in src.license.name
    assert src.commercial_use_allowed is True
    assert src.redistribution_allowed is True
    assert src.modifications_allowed is True
    assert src.sharealike_required is False


def test_legal_review_signed_off():
    src = _load()
    assert src.legal_review is not None
    assert src.legal_review.status.value == "reviewed"


def test_ingestion_block_points_at_real_client():
    """Catches a future rename of CtgovClient that forgets to update YAML."""
    src = _load()
    assert src.ingestion is not None
    assert src.ingestion.client == "knowledge_base.clients.ctgov_client.CtgovClient"
