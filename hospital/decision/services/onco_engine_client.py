"""Adapter to OpenOnco rule engine.

In-process for MVP — swap method bodies for httpx calls if the engine
moves to a separate service.  All imports from knowledge_base stay here;
nothing outside this file should import directly from knowledge_base.engine.
"""

from __future__ import annotations


class OncoEngineClient:
    """Single point of contact with the OpenOnco core engine."""

    def __init__(self):
        self._civic_client = None
        self._civic_init_attempted = False

    def _get_civic_client(self):
        if self._civic_init_attempted:
            return self._civic_client
        self._civic_init_attempted = True
        try:
            from hospital.config import get_settings
            settings = get_settings()
            if not settings.FEATURE_CIVIC_LOOKUP:
                return None
            snap = settings.civic_snapshot_path
            if snap is None:
                return None
            from knowledge_base.engine.snapshot_civic_client import SnapshotCIViCClient
            self._civic_client = SnapshotCIViCClient(snap)
            import logging
            logging.getLogger(__name__).info("CIViC snapshot loaded: %s", snap)
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning("CIViC client init failed (fail-open): %s", exc)
        return self._civic_client

    def generate_plan(self, patient_dict: dict, *, kb_root) -> object:
        from knowledge_base.engine.plan import generate_plan as _fn
        civic = self._get_civic_client()
        return _fn(
            patient_dict,
            kb_root=kb_root,
            actionability_enabled=(civic is not None),
            actionability_client=civic,
        )

    def orchestrate_mdt(self, patient_dict: dict, result, *, kb_root) -> object:
        from knowledge_base.engine.mdt_orchestrator import orchestrate_mdt as _fn
        return _fn(patient_dict, result, kb_root=kb_root)


# Module-level singleton — import this, not the class directly
engine = OncoEngineClient()
