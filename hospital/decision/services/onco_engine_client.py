"""Adapter to OpenOnco rule engine.

In-process for MVP — swap method bodies for httpx calls if the engine
moves to a separate service.  All imports from knowledge_base stay here;
nothing outside this file should import directly from knowledge_base.engine.
"""

from __future__ import annotations


class OncoEngineClient:
    """Single point of contact with the OpenOnco core engine."""

    def generate_plan(self, patient_dict: dict, *, kb_root) -> object:
        from knowledge_base.engine.plan import generate_plan as _fn
        return _fn(patient_dict, kb_root=kb_root)

    def orchestrate_mdt(self, patient_dict: dict, result, *, kb_root) -> object:
        from knowledge_base.engine.mdt_orchestrator import orchestrate_mdt as _fn
        return _fn(patient_dict, result, kb_root=kb_root)


# Module-level singleton — import this, not the class directly
engine = OncoEngineClient()
