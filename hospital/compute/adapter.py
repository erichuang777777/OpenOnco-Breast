"""Adapter to external clinical compute tools repo.

The compute tools (CrCl, BSA, dose calculators, etc.) already exist in a
separate repo.  This module defines the interface contract; wire up the
actual implementations when the repo is available as a dependency or service.

Usage:
    from hospital.compute.adapter import compute
    crcl = compute.crcl(age=65, weight=70.0, scr=1.1, sex="female")
"""

from __future__ import annotations


class ComputeAdapter:
    """Interface to cross-sectional clinical calculation gadgets."""

    def crcl(self, age: int, weight: float, scr: float, sex: str) -> float:
        """Cockcroft-Gault creatinine clearance (mL/min).

        sex: "male" | "female"
        """
        raise NotImplementedError("Wire up to external compute repo")

    def bsa(
        self,
        height_cm: float,
        weight_kg: float,
        formula: str = "mosteller",
    ) -> float:
        """Body surface area (m²).

        formula: "mosteller" | "dubois"
        """
        raise NotImplementedError

    def carboplatin_auc_dose(self, auc: float, gfr: float) -> float:
        """Calvert formula: dose (mg) = AUC × (GFR + 25)."""
        raise NotImplementedError

    def chemo_dose(
        self,
        base_mg_per_m2: float,
        bsa: float,
        *,
        cap_mg: float | None = None,
        round_to: float = 1.0,
    ) -> float:
        """mg/m² → actual dose with optional cap and rounding."""
        raise NotImplementedError


# Module-level singleton
compute = ComputeAdapter()
