# KB Claim-Anchor Grounding Report

_Generated_: 2026-07-04T05:53:28.147957+00:00

Audit of claim-bearing prose fields on Indication, Regimen, and BiomarkerActionability entities. Layer 1 (detection) checks whether the parent entity cites ≥1 SRC-* anchor; Layer 2 (semantic, opt-in) asks the Claude API whether each cited source plausibly supports the claim. Tracks Q4/Q5 of `docs/plans/kb_data_quality_plan_2026-04-29.md`; v1.0 target ≥90% anchor coverage.

## Top-level metrics

| Metric | Numerator | Denominator | Score |
|---|---:|---:|---:|
| Claim-bearing fields with ≥1 anchor | 6 | 6 | 100.0% |

## Per-entity-type breakdown

| Entity type | Total claims | Anchored | Coverage |
|---|---:|---:|---:|
| biomarker_actionability | 6 | 6 | 100.0% |

## Detached claims (top 50 of 0)

_None — every claim-bearing field has at least one cited Source._
