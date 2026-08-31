# Full-cohort privacy receipts — frozen measurement (697aa6e)

**Evidence classification: HISTORICAL FROZEN MEASUREMENT, REVALIDATED FOR
CURRENT CONTRACT COMPATIBILITY.**

This directory preserves the receipts produced by the full-cohort privacy run of
2026-08-28 and the read-only revalidation that checked them against the current
product contract. The files were copied here byte-for-byte; nothing in them was
edited, regenerated or re-derived.

| | |
|---|---|
| Historical measurement commit | `697aa6ebcf691f39b486f384b1d6a3f7f84eb8af` |
| Current compatibility validator | `63437d20e493f09296af73f50348eb60fbe11030` |
| Receipts parsed and verified | 462 / 462 |
| Writes during revalidation | 0 |
| Original bytes | unchanged |
| Frozen run re-run | no |

## What this is, and what it is not

The run was executed once, on the measurement commit above, with the Gemma leg
live on a private Vertex endpoint. It is **not** a measurement of the current
product commit and must never be presented as one. The preregistration is bound
to this single frozen run: re-executing it would produce a new experiment rather
than confirm the old one, so it is never re-run.

What was done instead is a read-only compatibility check. The current tree's
production loader (`LockedJsonPrivacyReceiptSource`) read these stored bytes and
verified all 462 receipts — schema, producer, content hash, signature, payload
binding and full-audit gate — with a write guard installed for the duration.
The guard never fired, and the file hashes were recomputed afterwards and found
unchanged. Details and per-check counts are in `COMPATIBILITY_REPORT.md`;
`raw-run.json` is the machine-readable output of the same run.

## Population boundaries

The **462 receipts** here and the **180 records** of the frozen P1 privacy study
are separate populations with different denominators. No figure may combine
them, and no rate may be computed across them.

Public metrics for the P1 study come from
`artifacts/evidence/p1-frozen-001/p1-frozen-001.corrected-view.json` together
with the committed erratum `corpus/ERRATUM_001_p1-frozen-001.md` — not from the
raw report, whose arm-declaration labels were superseded by amendment 001.

## Findings from the compatibility report, and where they stand

`COMPATIBILITY_REPORT.md` is a frozen document: it records the state at the
moment of revalidation and is never edited afterwards. Two of the four findings
it lists were resolved by the commit that created this directory. This table is
the current status; read it alongside the report, not instead of it.

| # | Finding in the report | Status |
|---|---|---|
| 1 | Receipts existed only in a temporary directory | **RESOLVED by `7879ca06`** — byte-exact durable copy committed here |
| 2 | A two-receipt smoke result sat at the canonical evidence path | **RESOLVED by `7879ca06`** — relocated to `artifacts/evidence/dev-only/local-smoke-2-receipts-8c57375/` and explicitly excluded from all submission material |
| 3 | Published P1 arm labels must come from the corrected view | **PRESENTATION RULE** — use `p1-frozen-001.corrected-view.json` plus `corpus/ERRATUM_001_p1-frozen-001.md`; the raw report's arm declarations were superseded by amendment 001 |
| 4 | 462 receipts and 180 P1 records are separate populations | **PRESENTATION RULE** — never combined, never used as one denominator |

## Retention rule for the temporary originals

The Temp originals of `privacy-receipts.json` and `RUN_MANIFEST.json` are still
in place and **must not be deleted yet**. This evidence currently exists in one
local feature-branch commit only. They may be removed once that commit has been
pushed to a secure remote and the hashes above have been reproduced from a clean
checkout of it. Merge and push remain owner-controlled decisions.

## Files

| File | What it is |
|---|---|
| `privacy-receipts.json` | The receipt wire, exactly as produced by the frozen run |
| `RUN_MANIFEST.json` | The run's own manifest: hashes, locus, timings, code provenance |
| `COMPATIBILITY_REPORT.md` | Human-readable revalidation report |
| `raw-run.json` | Machine-readable revalidation output |
| `SHA256SUMS.txt` | Digests of every file above |

The signing key is held outside every repository. Only the verifier-lock
fingerprint appears in this evidence, which is the value the run manifest itself
carries; the key, its path and any digest of it are deliberately absent.

The run's input corpus is not copied here: it is tracked in git at the
measurement commit and recoverable with
`git show 697aa6ebcf691f39b486f384b1d6a3f7f84eb8af:corpus/onboarding/notes.json`
(sha256 `ce71a0b7b50601148c49b65457bc603efca929b3569ed37179902424c8d36af6`, the
value pinned inside `RUN_MANIFEST.json`).

All records in this evidence are synthetic. No real person, institution record
or contact detail appears anywhere in it.
