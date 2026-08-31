# Frozen measurement — current-contract compatibility revalidation

**Verdict: PASS.** The frozen Gemma measurement parses, verifies and round-trips
without drift under the current production contract code, and its bytes are
unchanged.

The frozen run was **not** re-executed. The preregistration is bound to a single
frozen run; re-running it would produce a new experiment rather than confirm the
old one. This is a read-only compatibility check of stored bytes.

| | |
|---|---|
| Original measurement commit | `697aa6ebcf691f39b486f384b1d6a3f7f84eb8af` |
| Current validator commit | `63437d20e493f09296af73f50348eb60fbe11030` |
| Evidence class | HISTORICAL FROZEN MEASUREMENT |
| Current-tree status | REVALIDATED FOR CURRENT CONTRACT COMPATIBILITY |
| Frozen run re-executed | no |
| Write attempts during validation | 0 (write guard installed; any attempt would have raised) |
| Original bytes unchanged | yes (hashes recomputed after validation, all identical) |

## What was executed

The receipts were loaded through `LockedJsonPrivacyReceiptSource` from the
current tree — the same class the scheduler uses in production — which chains
the source-hash lock, the verifier-lock fingerprint, wire-shape validation,
`parse_artifact` against `PRODUCER_REGISTRY`, `verify_privacy_receipt`, and the
full-audit privacy-receipt gate. A second per-receipt pass recorded the detail
below. A write guard wrapped `open`, `os.replace/rename/remove/unlink/mkdir`
and the `Path` write methods for the whole validation; it never fired.

## Results

**Production loader:** PASS — 462 receipts loaded, no fallback, no duplicate
case. Source lock resolved to `source_sha256 =`
`70ccfc251d37dffa8174d82842feedcef1227399a285d13b9ba9e82979fab901`,
`key_id = full-cohort-receipt-run-v1`, `algorithm = HMAC-SHA256`,
`key_fingerprint_sha256 =`
`fa70a3d2d397209ea3fb6f5b09363e3b5cfc2bf6a0742c0f3ca7932031b92b08`.

| Check | Result |
|---|---|
| Artifact count | 462 |
| Parse success / failure | 462 / 0 |
| Signature valid / invalid | 462 / 0 |
| Semantic drift (canonical round-trip differs) | 0 |
| Schema | `PrivacyReceipt/1.1.0` (single value across all 462) |
| Producer | `local-privacy-gate@0.1.0`, identity `privacy-gate` (single value) |
| Decision | `ACCEPTED` (single value) |
| Data mode | `SYNTHETIC` (single value) |
| Execution locus | `LAB_LOCAL / PRIVATE_SERVICE / OLLAMA_VERTEX_ENDPOINT / gemma4:e4b-it-qat` (single value) |
| Signature algorithm | `HMAC-SHA256` (single value) |
| Payload binding present (input closure) | 462 / 462 bound, 0 unbound |

Content-hash conformance is covered by `parse_artifact`, which recomputes each
envelope's `content_hash` and refuses a mismatch; all 462 passed. Semantic drift
was measured by comparing `canonical_json_bytes` of the stored wire against the
current contract's re-serialisation of the parsed artifact — byte-identical for
every receipt, so the current contract neither drops nor rewrites any field.

**Cohort manifests** (own provenance, not the current live run):

| Manifest | Schema | Source commit | Parse | Drift |
|---|---|---|---|---|
| `c1-manifest.json` | `CohortDayManifest/3.0.0` | `2d8bebbe97794865f77f037dea518a39e8f75e38` | PASS | none |
| `c2-manifest.json` | `CohortDayManifest/3.0.0` | `b5cd5a815baad5980a3d62bfb49ab980b63e3057` | PASS | none |

## Inventory (exact paths and sha256)

| Item | sha256 |
|---|---|
| frozen run receipts — `intv4-697aa6e/artifacts/evidence/full-cohort-receipts/privacy-receipts.json` | `70ccfc251d37dffa8174d82842feedcef1227399a285d13b9ba9e82979fab901` |
| frozen run manifest — `.../full-cohort-receipts/RUN_MANIFEST.json` | `a429a247ba4ee9da2653a2d5c91db5d210709014e55c18c07870e54782183924` |
| frozen run input corpus — `corpus/onboarding/notes.json` (tracked at `697aa6e`) | `ce71a0b7b50601148c49b65457bc603efca929b3569ed37179902424c8d36af6` |
| P1 report (raw manifest) — `artifacts/evidence/p1-frozen-001/p1-privacy-report.json` | `95fbece58f848b24fdcce5d26597a1c05cd11b51faeea8e11d6f503ac8edfd8a` |
| P1 corrected view — `.../p1-frozen-001.corrected-view.json` | see `raw-run.json` |
| P1 records — `.../records.jsonl` | see `raw-run.json` |
| Erratum — `corpus/ERRATUM_001_p1-frozen-001.md` | see `raw-run.json` |
| c1 manifest (authoritative tree) | `093f4bff34db09278dde20cfdb540ad62256e9c7efba6aa0a4b5d400cb5e6b3d` |
| c2 manifest (authoritative tree) | `113f6e5e0c433e9512012cca6542c27dd3629743b72818241f681e3d37e84ab9` |

The signing key lives outside every repository; neither its path nor any digest
of it is published here. Only the verifier-lock fingerprint appears, which is
the value the manifest itself carries.

Full machine-readable output: `raw-run.json` beside this file.

## Findings that need action

1. **The frozen receipts exist in exactly one place, and it is a temporary
   directory.** `privacy-receipts.json` and `RUN_MANIFEST.json` are untracked
   and live only under `AppData\Local\Temp\claude\...`. The run cannot be
   re-executed, so a temp cleanup would destroy irreplaceable evidence. They
   need a durable home. (The input corpus is safe: it is tracked in git at
   `697aa6e`.)

2. **A decoy sits at the canonical evidence path.** The L3 lane worktree holds
   `artifacts/evidence/full-cohort-receipts/` containing a 2-receipt local smoke
   result (`receipt_count: 2`, `posture: local`,
   `code_source_commit: 8c57375ee0a3704885f4214790d1d27d2a23c480`,
   sha256 `899456f1c23bf33744a1da8681295ecff8a20332353431fc1d687b3e44475268`).
   It is untracked and, unlike the lease/checkpoint files, **not** gitignored.
   Anyone reading that path would find a file that looks like the run and is
   not. It should be removed or renamed.

3. **Published P1 arm labels must come from the corrected view.** In the raw
   report the 136/180 arm (`surface_exact_search`) is labelled
   *declared secondary, exploratory*; under amendment 001 the corrected view
   makes it **primary**, with `model_offsets` as the fully-reported secondary.
   Only the arm-declaration labels and `limitations[4]` differ — both files
   carry the same `content_hash`
   (`a3225fe849562e0ecf77fb4e608f72619daf31ae0f769968b0f892faabaa3a6d`), so no
   measured value moved. Any surface currently rendering the raw label is
   showing a superseded declaration.

4. **Denominators must not be merged.** 462 is the receipt-run case count;
   180 is the frozen P1 record count. They are different populations and no
   figure may combine them.
