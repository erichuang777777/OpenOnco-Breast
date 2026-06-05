"""HIS adapter interface (stub) — Phase B3.

This repo defines the interface contract only.
The real crawler implementation lives in a separate repo.
Pattern mirrors hospital/compute/adapter.py.
"""

from __future__ import annotations


class HisAdapter:
    """Abstract interface for HIS data retrieval.

    All methods raise NotImplementedError — production implementations
    override this class and are configured via dependency injection.
    """

    def get_patient_appointments(self, mrn: str) -> list[dict]:
        raise NotImplementedError("HIS adapter not configured")

    def get_patient_medications(self, mrn: str) -> list[dict]:
        raise NotImplementedError("HIS adapter not configured")

    def get_lab_results(self, mrn: str) -> list[dict]:
        raise NotImplementedError("HIS adapter not configured")

    def get_imaging_results(self, mrn: str) -> list[dict]:
        raise NotImplementedError("HIS adapter not configured")


his_adapter = HisAdapter()
