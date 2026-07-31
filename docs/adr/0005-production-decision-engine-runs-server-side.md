# 0005 — Production decision engine runs server-side; the Pyodide demo stays a browser showcase

Two things, decided together:

1. The `openonco.info` Pyodide demo (`try.html`) exists to let a visitor try the engine in-browser with zero install. It is a **showcase**, not the production deployment path.
2. For real clinical use, **correctness of the decision engine takes priority over keeping patient data client-side.** The CQL/ELM decision-logic layer (replacing the prose-condition `Algorithm.decision_tree`, see `docs/reviews/fable-opinion.md`) compiles and executes on the JVM reference toolchain (`cqframework`). There is no requirement to also ship a browser-compatible (`cql-execution`) subset engine to preserve a "never leaves the browser" property for production traffic.

## Why

The Pyodide demo's "no backend, no patient data leaves the device" property was a nice-to-have for the public showcase, not a load-bearing clinical-safety mechanism — nothing in CHARTER or the existing ADRs makes it one. ADR-0003's actual requirement (CHARTER §9.3) is narrower: no patient data in **public** artifacts (repo, build output, gallery, third-party integrations). It does not forbid a controlled, access-audited server from processing patient data — Hospital Edition already does this today (`hospital/` FastAPI backend: patient registration, timeline events, AuditLog, per `DEVELOPMENT_PLAN.md`).

Maintaining two execution engines (a JS subset for the browser, the JVM reference for the server) to preserve a privacy property the production system doesn't actually need would mean permanently tracking `cql-execution`'s smaller feature surface against the full CQL the KB uses, and debugging the same clinical logic through two runtimes with different edge-case behavior — to protect a guarantee (patient-data locality) the real deployment target, a server, was never going to provide anyway. That cost buys no additional clinical safety; it only protects the demo's marketing line, which stays true regardless because the demo keeps its current architecture.

## Consequences

- CQL-to-ELM compilation and ELM execution both standardize on `cqframework` (JVM). No JS execution engine is a dependency of the production path.
- `openonco.info`'s static Pyodide demo (`try.html`) keeps running today's YAML + Python engine as-is. It is explicitly a showcase — it does not need to track parity with the CQL migration, and the CQL migration does not need to keep it working. If the two diverge, that's expected, not a bug.
- Public-facing copy ("no patient data leaves the device") must stay scoped to the demo specifically, not generalized to "OpenOnco" as a whole. `README.md` and the wiki `Introduction` page carry a one-line clarification so a reader can't mistake the demo's property for a system-wide guarantee.
- Any server path that receives real patient data — today's Hospital Edition, and the future CQL execution service — must go through the existing AuthN/AuthZ + `AuditLog` discipline locked in `DEVELOPMENT_PLAN.md`. This ADR does not create a new allowance to log or store patient data anywhere; it only removes the requirement that the decision engine itself run client-side.
- This does not relax ADR-0003. Public-artifact exposure (repo, build output, gallery) is still forbidden regardless of where the engine executes.
