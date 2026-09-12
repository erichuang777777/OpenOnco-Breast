"""Ad-hoc end-to-end scenario runner (read/run-only, not committed).

Drives the running uvicorn server through a breast-cancer patient workflow.
"""
from __future__ import annotations

import json
import sys

import httpx

BASE = "http://127.0.0.1:8765"
API = f"{BASE}/api/v1"
MRN = "REAL-TEST-001"

results: list[tuple[str, bool, str]] = []
errors: list[str] = []


def record(name: str, passed: bool, detail: str) -> None:
    results.append((name, passed, detail))
    status = "PASS" if passed else "FAIL"
    print(f"[{status}] {name}")
    print(f"        {detail}")


def mk_token() -> str:
    from hospital.auth.jwt_utils import create_access_token

    return create_access_token(
        sub="dr-lin-e2e",
        email="dr.lin@clinic.example",
        name="Dr Lin",
        role="clinic_hcp",
    )


def main() -> int:
    token = mk_token()
    print(f"JWT created for clinic_hcp user (len={len(token)})\n")
    headers = {"Authorization": f"Bearer {token}"}
    client = httpx.Client(timeout=30.0)

    fhir_patient = {
        "resourceType": "Patient",
        "id": "twcore-real-001",
        "identifier": [
            {
                "type": {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/v2-0203",
                            "code": "MR",
                        }
                    ]
                },
                "value": "REAL-TEST-001",
            }
        ],
        "name": [{"use": "official", "text": "林素珍"}],
        "gender": "female",
        "birthDate": "1975-03-12",
    }

    # ── Step a: FHIR import ──────────────────────────────────────────────
    try:
        r = client.post(
            f"{API}/fhir/Patient/$import",
            headers=headers,
            json={"resource": fhir_patient},
        )
        ok = r.status_code == 200
        body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        detail = (
            f"HTTP {r.status_code} | action={body.get('action')} "
            f"mrn={body.get('mrn')} masked_name={body.get('masked_name')} "
            f"sex={body.get('sex')} dob_year={body.get('dob_year')} "
            f"warnings={body.get('warnings')}"
        )
        record("a. FHIR Patient $import", ok and body.get("mrn") == MRN, detail)
    except Exception as e:  # noqa: BLE001
        errors.append(f"step a: {e!r}")
        record("a. FHIR Patient $import", False, f"EXCEPTION {e!r}")

    # ── Step b: verify patient ───────────────────────────────────────────
    try:
        r = client.get(f"{API}/patients/{MRN}", headers=headers)
        ok = r.status_code == 200
        body = r.json() if ok else {}
        detail = (
            f"HTTP {r.status_code} | mrn={body.get('mrn')} "
            f"masked_name={body.get('masked_name')} status={body.get('status')} "
            f"sex={body.get('sex')} dob_year={body.get('dob_year')}"
        )
        record("b. GET patient by MRN", ok and body.get("mrn") == MRN, detail)
    except Exception as e:  # noqa: BLE001
        errors.append(f"step b: {e!r}")
        record("b. GET patient by MRN", False, f"EXCEPTION {e!r}")

    # ── Step c: POST timeline doctor_note ────────────────────────────────
    try:
        r = client.post(
            f"{API}/patients/{MRN}/timeline",
            headers=headers,
            json={
                "event_type": "doctor_note",
                "title": "Initial consult: HER2+ metastatic breast cancer",
                "body_json": {
                    "note": "Stage IV HER2-positive (IHC 3+) invasive ductal carcinoma. "
                    "Visceral (hepatic) metastases on staging CT. ER/PR negative. "
                    "Plan: first-line anti-HER2 doublet + taxane. Await echo for LVEF baseline.",
                    "ecog": 1,
                },
            },
        )
        ok = r.status_code == 201
        body = r.json() if ok else {}
        detail = (
            f"HTTP {r.status_code} | id={body.get('id')} "
            f"event_type={body.get('event_type')} title={body.get('title')!r} "
            f"source={body.get('source')}"
        )
        record("c. POST timeline doctor_note", ok and body.get("event_type") == "doctor_note", detail)
    except Exception as e:  # noqa: BLE001
        errors.append(f"step c: {e!r}")
        record("c. POST timeline doctor_note", False, f"EXCEPTION {e!r}")

    # ── Step d: GET reminders (expect empty) ─────────────────────────────
    try:
        r = client.get(f"{API}/patients/{MRN}/reminders", headers=headers)
        ok = r.status_code == 200
        body = r.json() if ok else []
        is_empty = isinstance(body, list) and len(body) == 0
        detail = f"HTTP {r.status_code} | count={len(body) if isinstance(body, list) else 'n/a'} (expected 0)"
        record("d. GET reminders (empty initially)", ok and is_empty, detail)
    except Exception as e:  # noqa: BLE001
        errors.append(f"step d: {e!r}")
        record("d. GET reminders (empty initially)", False, f"EXCEPTION {e!r}")

    # ── Step e: trials search ────────────────────────────────────────────
    try:
        r = client.get(
            f"{API}/trials",
            headers=headers,
            params={"condition": "breast cancer", "intervention": "trastuzumab"},
        )
        # Graceful = any of: 200 with list, or a non-500 error envelope.
        graceful = r.status_code != 500
        body = None
        try:
            body = r.json()
        except Exception:  # noqa: BLE001
            body = r.text[:200]
        if r.status_code == 200 and isinstance(body, list):
            sample = body[0].get("nct_id") if body else "<none>"
            detail = f"HTTP 200 | trials_returned={len(body)} first_nct={sample}"
            passed = True
        else:
            detail = f"HTTP {r.status_code} | body={str(body)[:200]} (non-500 => graceful)"
            passed = graceful
        record("e. GET trials search", passed, detail)
    except Exception as e:  # noqa: BLE001
        # Network failure reaching CT.gov is acceptable as long as it's caught.
        errors.append(f"step e: {e!r}")
        record("e. GET trials search", False, f"EXCEPTION {e!r}")

    # ── Step f: plan pdf 404 for non-existent plan ───────────────────────
    try:
        r = client.get(f"{API}/plan/nonexistent-plan-xyz/pdf", headers=headers)
        ok = r.status_code == 404  # must be 404, not 500
        detail = f"HTTP {r.status_code} | body={r.text[:160]} (expected 404, not 500)"
        record("f. GET plan/{id}/pdf -> 404", ok, detail)
    except Exception as e:  # noqa: BLE001
        errors.append(f"step f: {e!r}")
        record("f. GET plan/{id}/pdf -> 404", False, f"EXCEPTION {e!r}")

    # ── Step g: patients stats ───────────────────────────────────────────
    try:
        r = client.get(f"{API}/patients/stats", headers=headers)
        body = None
        try:
            body = r.json()
        except Exception:  # noqa: BLE001
            body = r.text[:200]
        ok = r.status_code == 200
        detail = f"HTTP {r.status_code} | body={str(body)[:200]}"
        record("g. GET patients/stats", ok, detail)
    except Exception as e:  # noqa: BLE001
        errors.append(f"step g: {e!r}")
        record("g. GET patients/stats", False, f"EXCEPTION {e!r}")

    client.close()

    # ── Summary ──────────────────────────────────────────────────────────
    total = len(results)
    passed = sum(1 for _, p, _ in results if p)
    failed = total - passed
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total steps: {total}")
    print(f"Passed:      {passed}")
    print(f"Failed:      {failed}")
    if failed:
        print("Failed steps:")
        for name, p, detail in results:
            if not p:
                print(f"  - {name}: {detail}")
    if errors:
        print(f"Errors/exceptions ({len(errors)}):")
        for e in errors:
            print(f"  - {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
