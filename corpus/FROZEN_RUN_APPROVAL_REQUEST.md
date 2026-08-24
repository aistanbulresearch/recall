# Frozen-run approval request

- Status: **submitted for auditor approval**; the frozen test split has not been read
- Date: 2026-08-23
- Lane: L3
- Governs: the single permitted run on the frozen `test` split
- Preregistration: `corpus/PREREGISTRATION.md`, amended by `corpus/PREREGISTRATION_AMENDMENT_001.md`
- Prediction protocol: `corpus/PREDICTION_budget_run.md`

On approval, the approval record is written into the `preregistration_approval`
field of the frozen run's evidence manifest, and the frozen split is read exactly
once.

## 1. The six bound values

The approval is bound to these six. If any one of them changes, the approval
lapses and a new one is required. Every value is recorded in each evidence
manifest, so a reviewer checks the binding against the artifact rather than
against this document.

| # | Value | Bound to |
|---|---|---|
| 1 | `prompt_sha256` | `90108cca831ab6fbc4aca2a60969a7b4520b19061968697c24d4f2166a7dafb5` |
| 2 | `adapter_version` and model identity | `gemma-span-adapter@1.1.0`; `registry.ollama.ai/library/gemma4@e4b-it-qat`, quantisation `q4_0`, file `sha256-e8b6a059ba86947a44ace84d6e5679795bc41862c25c30513142588f0e9dba1d` |
| 3 | `locator_version` and strategy | `surface-exact-search-locator@1.0.0`. Exact substring search over the note text, case sensitive, no normalisation, overlaps included. One occurrence places the span there; several occurrences each become their own candidate proposal, counted separately including as false positives; no occurrence refuses that one proposal with `model_response_surface_not_found` and leaves the rest of the response intact. |
| 4 | Acceptance thresholds | **Unchanged from section 6.** Reproduced verbatim below. |
| 5 | Three split hashes | `dev` `05c1dc8f033fd9a90b59204cb0c4dfb23b13fd41f4bcf79e7fc9cdcfbb37bcb5`; `test` `ef5796b16e037cb59aad2513f1ada62e1e2bef9b67cd97a9a9a7c3d53ebe8dfe`; `train` `4f03932c103149f525f2c1d059e9b38abad359bd5604113529dc61a240d7e1a0` |
| 6 | Runtime configuration | `reasoning_effort` = `think=false` on the native route; `format` = `json`; `timeout_seconds` = 900; `num_predict` = **1024**, previously 512; defect-fix commit `5de7c3701db58ab9492717c6c43ff46a5bf21d6b`, locked by `d2085c4a21f535b179cd78f330ce5194930bba02`; also `num_ctx` 2048, `num_thread` 14, `concurrency` 3, `keep_alive` 30m |

All six values are declared in `corpus/FROZEN_CONFIG.json`, sha256
`80333f1b3022f205fff238360a5a48884d7b73980e1f550af939fa8c22a1b069`. That file is the machine-checked form of this table:
the harness compares the effective configuration against it before processing a
single record and refuses the run on any mismatch, naming the field
(`feat(privacy): assert the frozen configuration before any run`, commit
`a32b154d0985d0255e1dede7c87342288bd60b84`). The frozen run cannot start without
passing that check.

### Item 4, verbatim from section 6

1. **Mandatory safety gate.** Zero seeded direct-identifier spans in accepted
   payloads. A single escape fails the protocol regardless of every other result.
2. The local model earns a demo claim only if it contributes at least one
   incremental true positive on the frozen test split **and** does not increase
   accepted escapes.
3. Every invalid JSON, timeout, unavailable model, or uncertain span must
   quarantine or remain blocked by the deterministic outbound gate.
4. If the model contributes no incremental true positive, increases escapes, or
   cannot complete inside the allocated privacy segment, it is removed from the
   demo critical path. The deterministic Privacy Gate stays.

Unchanged from section 6. Amendment 001 changes which arm is measured against
these thresholds; it does not relax, re-derive, or restate any threshold value.

### Note on item 6

The `num_predict` correction was previously carried only by a command-line
argument, which meant a forgotten flag would have silently restored the defect.
Commit `5de7c3701db58ab9492717c6c43ff46a5bf21d6b` moves the corrected value into
the code default, so the frozen run inherits it without depending on an argument.
The configuration does not change; the default is brought into line with the
frozen value.

Two layers now guard it rather than code review alone:

- commit `d2085c4a21f535b179cd78f330ce5194930bba02` adds a test asserting the
  code default is 1024, so a regression fails the suite;
- commit `a32b154d0985d0255e1dede7c87342288bd60b84` adds the startup check
  described above, so a drifted value stops the run before any record is
  processed.

Both refusals are exercised by tests. A demonstration on the frozen split path,
with only `num_predict` altered in the frozen configuration, exits 1 with
`frozen_config_mismatch:transport.options.num_predict expected=512 actual=1024`
and creates no evidence directory.

## 2. The frozen test split has not been read

The frozen test split has not been read; manifest hash
`ef5796b16e037cb59aad2513f1ada62e1e2bef9b67cd97a9a9a7c3d53ebe8dfe`.

That value is the hash declared for the `test` split in
`corpus/PRIVACY_CORPUS_MANIFEST.json`, and it matches the file
`corpus/generated/test.json` byte for byte, verified on 2026-08-23.

Supporting evidence from inside the artifacts themselves: every recorded run
carries `split_sha256 = 05c1dc8f033fd9a90b59204cb0c4dfb23b13fd41f4bcf79e7fc9cdcfbb37bcb5`,
which is the manifest hash of the **dev** split. The artifacts therefore
demonstrate from their own contents which split was read.

The harness refuses a frozen-split run without a recorded approval and a
`frozen_test_run_id`, and refuses a second frozen run outright. Those refusals
are exercised by tests, not asserted in prose.

## 3. Both arms will be published together

Both arms are published in full, including arm A's zero. The commitment is
unconditional and does not depend on which arm looks better on the frozen split.

Development split, 72 records, one model call per record scored on both arms:

| | arm A `model_offsets` | arm B `surface_exact_search` |
|---|---|---|
| incremental true positives | **0** | +173 |
| incremental false positives | **+349** | +5 |
| accepted payloads | 0 of 72 | 57 of 72 |
| accepted escapes | 0 | 0 |
| exact recall | 0.7824, identical to the deterministic baseline | 0.9826 |

Arm A contributes nothing and its false positives rose as the completion budget
grew: with more room it proposes more spans and places all of them wrongly. That
result is reported wherever arm B is reported.

## 4. Position on the declaration timestamp

The following is the auditor's ruling, reproduced verbatim:

> Declaration commit post-dates run start by 42 minutes; working-tree history cannot independently corroborate pre-declaration. This claim is therefore NOT relied upon. The promotion's validity rests solely on (a) verified unread frozen split [manifest hash], (b) dev split's role as configuration selection, (c) full publication of both arms including Arm A's zero incremental result.

The bracketed value in clause (a) is
`ef5796b16e037cb59aad2513f1ada62e1e2bef9b67cd97a9a9a7c3d53ebe8dfe`.

The interval is measured 41m49s; quoted as 42 minutes in the auditor's paragraph
above.

`adapter_version = gemma-span-adapter@1.1.0` and `prompt_sha256 = 90108cca…` are
retained as evidence for one claim only: that the measurement was produced with
the declared configuration. They are not evidence of when the configuration was
declared and are not cited as such.

## 5. One run

The frozen test split is measured in exactly one run, carrying a
`frozen_test_run_id` recorded in its evidence manifest and in section 9 of the
preregistration. The harness refuses to start a second frozen-split run. A
replacement requires a new auditor approval, a new `frozen_test_run_id`, and an
explicit recorded statement of which run it supersedes and why. The superseded
manifest is retained, never deleted or overwritten.

## 6. Prediction protocol record

The last development run was the first application of the predict-before-run
rule. The prediction was committed as
`507806b0e60f187753124acaa77ab4b2a35f0532` at `2026-08-23T13:06:14Z`, and the run
started at `2026-08-23T13:06:59Z`, 45 seconds later.

Configuration and preregistration are committed before the run they govern, on
every lane, without exception. A run whose governing commit does not precede its
start time is a process failure and is reported as such.

## Development-split summary

### Prediction against result

| Clause | Threshold | Result | |
|---|---|---|---|
| previously truncated records returning valid JSON | at least 22 of 24 | **24 of 24** | holds |
| arm B incremental true positives | at least +150 | **+173** | holds |
| accepted escapes on every path | 0 | **0** | holds |

The run recorded no invalid response at all: 72 of 72 `OK`. Latency p50 358.6 s,
p95 470.8 s, maximum 562.8 s against a 900 s deadline, so the tolerance built into
clause 1 was not needed.

### Both arms, by language

| Path | Combined | Turkish | English |
|---|---|---|---|
| baseline recall | 0.7824 | 0.7824 | 0.7824 |
| baseline accepted | 0 of 72 | 0 of 36 | 0 of 36 |
| structured-only egress accepted | 72 of 72 | 36 of 36 | 36 of 36 |
| arm A recall | 0.7824 | 0.7824 | 0.7824 |
| arm A false positives | 357 | 171 | 186 |
| arm A accepted | 0 of 72 | 0 of 36 | 0 of 36 |
| **arm B recall** | **0.9826** | **0.9838** | **0.9815** |
| arm B true positives | 849 of 864 | 425 of 432 | 424 of 432 |
| arm B false positives | 13 | 5 | 8 |
| arm B accepted | 57 of 72 | 29 of 36 | 28 of 36 |
| arm B false quarantine | 12 | 4 | 8 |
| escapes, every path | 0 | 0 | 0 |

Mandatory safety gate: **PASS** on baseline, structured-only egress, and the
model comparison.

### Chain of custody for that run

| Link | Value |
|---|---|
| prediction commit | `507806b0e60f187753124acaa77ab4b2a35f0532` |
| commit time | `2026-08-23T13:06:14Z` |
| run start | `2026-08-23T13:06:59Z` |
| run end | `2026-08-23T15:35:08Z` |
| manifest sha256 | `c3f4cc54db08b077710b213443f39db89f5b0718714d15e2b79d86fd5ec73207` |
| manifest content hash | `9d8724420cdec654baf747a4f4c010df56eb9ff42de1754580b362cd88a47e98` |
| evidence commit | `e9533f7` |

## Limitations carried forward

- Synthetic corpus only. No real, clinical, or regulatory privacy claim is
  supported.
- The residual identifier rate is a property of the committed corpus design, not
  an estimate for real institutional text.
- The outbound allowlist derives from the training split and reflects the
  synthetic template vocabulary, so the false-quarantine figure is partly a
  vocabulary-coverage measure.
- Structured-only egress acceptance is a property of the payload shape, not a
  detection result, and is never reported as detector or model performance.
- Turkish surfaces in this corpus carry no diacritics. Diacritic and
  mixed-orthography behaviour is unmeasured.
