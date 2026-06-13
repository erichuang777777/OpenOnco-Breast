"""Unit tests for the sign-off→YAML export helpers + institutional full text."""

from __future__ import annotations

from pathlib import Path

import yaml

from scripts.export_signoffs_to_yaml import _set_block, _render_block
from hospital.admin.services import clinical_review as cr

ENTRIES = [
    {"reviewer_id": "REV-A", "timestamp": "2026-06-13T00:00:00+00:00", "rationale": "ok"},
    {"reviewer_id": "REV-B", "timestamp": "2026-06-13T01:00:00+00:00", "rationale": "ok"},
]


def test_set_block_appends_when_absent():
    text = "id: IND-X\nevidence_level: high\n"
    out = _set_block(text, ENTRIES)
    parsed = yaml.safe_load(out)
    assert parsed["id"] == "IND-X"
    assert len(parsed["reviewer_signoffs"]) == 2
    assert parsed["reviewer_signoffs"][0]["reviewer_id"] == "REV-A"


def test_set_block_replaces_legacy_int():
    text = "id: ALGO-X\nreviewer_signoffs: 0\nnotes: hi\n"
    out = _set_block(text, ENTRIES)
    parsed = yaml.safe_load(out)
    assert isinstance(parsed["reviewer_signoffs"], list)
    assert len(parsed["reviewer_signoffs"]) == 2
    assert parsed["notes"] == "hi"  # other keys preserved


def test_set_block_output_is_valid_yaml():
    text = "id: REG-X\ncomponents: []\n"
    out = _set_block(text, ENTRIES)
    yaml.safe_load(out)  # must not raise
    assert "reviewer_signoffs:" in out


def test_render_block_roundtrips():
    parsed = yaml.safe_load(_render_block(ENTRIES))
    assert parsed["reviewer_signoffs"] == ENTRIES


def test_fulltext_surfaced_only_when_dir_supplied(tmp_path: Path):
    kb = "knowledge_base/hosted/content"
    eid = "IND-BREAST-HER2-POS-MET-1L-THP"

    # Without a fulltext dir → no fulltext on any citation.
    bundle = cr.build_review_bundle(kb, "indication", eid)
    assert all("fulltext" not in c for c in bundle["citations"])

    # With a dir containing <src>.md → that citation carries the text.
    src_id = bundle["citations"][0]["source_id"]
    ftdir = tmp_path / "ft"
    ftdir.mkdir()
    (ftdir / (src_id.lower().replace("-", "_") + ".md")).write_text("INSTITUTIONAL PASSAGE", encoding="utf-8")

    bundle2 = cr.build_review_bundle(kb, "indication", eid, fulltext_dir=ftdir)
    hit = next(c for c in bundle2["citations"] if c["source_id"] == src_id)
    assert hit["fulltext"] == "INSTITUTIONAL PASSAGE"
    assert hit["fulltext_institutional"] is True
