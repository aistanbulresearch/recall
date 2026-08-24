# Erratum 001, frozen run p1-frozen-001

- Status: **DRAFT, uncommitted, awaiting owner approval and external auditor confirmation**
- Date raised: 2026-08-24
- Lane: L3
- Concerns: `artifacts/evidence/p1-frozen-001/p1-privacy-report.json`
- Defect class: stale arm declaration in the manifest. Not a measurement defect.

The frozen run manifest carries arm primacy labels that were written before
`corpus/PREREGISTRATION_AMENDMENT_001.md` promoted `surface_exact_search` to
primary. The labels are wrong. Every measured value is unaffected, the frozen
split was read exactly once, and no bound value changed.

This erratum refers to the manifest by hash. It does not modify it.

## 1. Immutability declaration

The original manifest, the per-record checkpoint, and both run logs are
unmodified since the run wrote them at 2026-08-24T02:47:54Z. Hashes below were
computed fresh at the time of writing, not copied from the run report.

| Artifact | sha256 | Bytes | Last modified, UTC |
|---|---|---:|---|
| `p1-privacy-report.json` | `95fbece58f848b24fdcce5d26597a1c05cd11b51faeea8e11d6f503ac8edfd8a` | 46312 | 2026-08-24T02:47:54Z |
| `records.jsonl` | `d90175a7566460eb104c8033ce321394e64ce2243441ec669c6bff4ddb41170b` | 207234 | 2026-08-24T02:47:54Z |
| `frozen.out.log` | `fcd0b72d6f876dda56c386dea6585ee1fdb9828fcdbd840c76a9cc45ee18c4bc` | 13408 | 2026-08-24T02:47:54Z |
| `frozen.err.log` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | 0 | 2026-08-23T20:46:55Z |
| `out_of_band_probe.json` | `5dd40beae43bd06116d3e45e5b4b068aca37b50a812d4cc76768b06d2f44f423` | 1506 | 2026-08-23T21:39:18Z |

The manifest's own `content_hash` field reads
`a3225fe849562e0ecf77fb4e608f72619daf31ae0f769968b0f892faabaa3a6d`. Recomputing
that hash over the manifest body, with `content_hash` excluded exactly as the
producer does, returns the same value. The document is internally consistent and
has not been edited since it was signed.

`frozen.err.log` is zero bytes. Its hash is the sha256 of the empty string, which
is the published constant `e3b0c442...b7852b855`, so its emptiness is verifiable
rather than asserted.

## 2. The amendment preceded the run

The stale labels are a declaration defect, not a case of a rule being changed
after seeing a result. The amendment was in force before the run began:

| Event | Time, UTC |
|---|---|
| Amendment 001 committed, `0084e0d3f8e237bb8a0d4f2b779d41751cd263a3` | 2026-08-22T19:38:05Z |
| Auditor approval wiring committed, `7b141ca495e5dc812243fc26a6dc52bc6b8019c3` | 2026-08-23T20:46:36Z |
| Frozen run start | 2026-08-23T20:46:55Z |
| Frozen run end | 2026-08-24T02:47:54Z |

The amendment predates the run by more than 25 hours, and predates the approval
commit by more than 24 hours. The approval commit precedes the run start by 19
seconds.

The amendment timestamp was read from git at the time of writing rather than
copied from an earlier report.

## 3. Complete stale-field scan

Every leaf of the manifest was enumerated and inspected, not only the `arms`
block. The scan looked for two things: fields that state primacy, and fields that
imply it without stating it.

**This list is closed, not sampled.** The scan walked all 947 leaves of the
document programmatically, matched each path and value against primacy
vocabulary, and inspected every match by hand. It found exactly nine stale paths,
listed in full in section 3.1. Sections 3.2 and 3.3 record what was checked and
found not stale, so a reader can see the negative results as well as the positive
ones.

The justification for scanning exhaustively rather than reading the obvious block
is `$.limitations[4]`. It contains no arm name, sits far from the `arms` block,
and would have survived any correction that targeted only the declaration
structure.

### 3.1 Fields that are stale

| JSON path | Current value, incorrect | Correct value under amendment 001 |
|---|---|---|
| `$.arms.primary.arm` | `model_offsets` | `surface_exact_search` |
| `$.arms.primary.status` | `preregistered primary` | primary under amendment 001 |
| `$.arms.primary.description` | describes scoring the offsets the model returned | describes placing each returned surface by deterministic exact search |
| `$.arms.secondary.arm` | `surface_exact_search` | `model_offsets` |
| `$.arms.secondary.status` | `declared secondary, exploratory` | secondary under amendment 001, fully reported |
| `$.arms.secondary.description` | describes surface placement | describes scoring the model's own offsets |
| `$.arms.secondary.ambiguity_rule` | the surface-placement ambiguity rule | belongs with `surface_exact_search`, so it moves to `$.arms.primary` |
| `$.limitations[4]` | "Approved residual span counts follow the primary arm, because the gate adjudicates the offsets the model returned." | the count follows `model_offsets`, which under amendment 001 is the secondary arm, so the sentence must name the arm rather than call it primary |

`$.limitations[4]` is the least obvious of these and the most important to catch.
It does not name an arm. It says "the primary arm" and then describes arm A
behaviour, which was self-consistent before the amendment and is self-contradictory
after it. A reader correcting only the `arms` block would leave this sentence
asserting the opposite of the corrected labels.

### 3.2 The gate pointer is NOT stale, and the defect must not be named as if it were

The working description of this defect has been "stale arm declaration and gate
pointer". The second half is wrong, and this erratum does not repeat it.

`$.mandatory_safety_gate` contains exactly five fields: `rule`,
`baseline_escapes`, `structured_only_escapes`, `comparison_escapes`, and
`result`. None of them carries an arm label, an arm name, or a pointer to an
arm. The gate verdict is not expressed in terms of primacy and is therefore not
stale.

`$.measurement_constraints.acceptance_thresholds` was also checked in full. Its
four rules are the section 6 text quoted verbatim and are arm agnostic. Its
`status` field already reads "unchanged from section 6; amendment 001 changes
which arm is measured, not these thresholds", so that block is amendment aware
and correct as written.

`$.evidence_scope`, `$.incremental_arm_a`, `$.incremental_arm_b`,
`$.comparison_arm_a`, and `$.comparison_arm_b` name arms as data containers, not
as ranks. They are correct and require no change.

### 3.3 One finding that is neither stale nor clean, recorded for the auditor

`$.mandatory_safety_gate.comparison_escapes` carries no arm label, but the
harness derives it from arm A alone. In `scripts/privacy_eval.py` the value is
taken from the `model_offsets` metrics.

In this run the point is moot: escapes are zero on every path, so the gate
verdict PASS is correct whichever arm the field is read from, and rule 1 is
satisfied for both arms independently. The observation is recorded because the
field's provenance is undeclared, and a future run where the two arms differ on
escapes would make an unlabelled arm A figure misleading.

This is not proposed as part of the correction. It is a harness observation for
the auditor to rule on separately, and it is not something the corrected view
touches.

## 4. Root cause

The `ARM_DECLARATION` constant in `scripts/privacy_eval.py` was written before
amendment 001 and carries no reference to it, and the locked-configuration assert
covered measurement parameters rather than declaration fields.

### 4.1 The constant is still stale as this erratum is written

A sweep of every surface that restates the arm declaration was run before this
erratum was committed. It found that `ARM_DECLARATION` in
`scripts/privacy_eval.py` still reads `"status": "preregistered primary"` against
`model_offsets`. This erratum does not fix it, because correcting the constant is
separate work that is not covered by the approval for this document.

The consequence is stated plainly so that nobody reads this erratum as closing the
defect at its source: any future run of the harness in its present state would
emit the same stale declaration. The correction of the constant, and the standing
rule that declaration fields must be derived from the governing document rather
than restated as free-standing literals, are tracked outside this erratum.

The same sweep confirmed that `corpus/PREREGISTRATION.md` carries the
pre-amendment arm table at section 4 but immediately follows it with an explicit
"Superseded by amendment 001 on 2026-08-22" paragraph naming the promotion, so
that document is self-correcting and needs no change here.

## 5. No second run

The frozen test split was read exactly once, by run `p1-frozen-001`, and will not
be read again. This erratum involves no model invocation, no re-scoring, and no
new measurement. The corrected view in section 6 is a mechanical relabelling of a
document that already exists.

`corpus/generated/test.json` remains at
`ef5796b16e037cb59aad2513f1ada62e1e2bef9b67cd97a9a9a7c3d53ebe8dfe`, matching the
manifest declaration and the run's recorded `split_sha256`.

## 6. Corrected view, derived by machine

`scripts/derive_corrected_view.py` reads the original manifest and amendment 001
and writes `p1-frozen-001.corrected-view.json`. It changes arm declaration labels
and nothing else.

The script does not take that claim on trust. It enumerates every leaf of both
documents, compares them, and exits without writing if any path outside a declared
correction set differs. It also refuses to run if the amendment file is missing,
and refuses if the manifest does not actually carry the pre-amendment labels, so
it cannot invent a correction for a document that does not need one.

Dry run output:

```
source manifest      : p1-privacy-report.json  sha256 95fbece58f848b24fdcce5d26597a1c05cd11b51faeea8e11d6f503ac8edfd8a
derivation script    : derive_corrected_view.py  sha256 ea1a5b7ab6ce59d9647ddeb1326a0c3297b8c9f8d8db88b70b6256fbbd27f4bd
corrected view       : p1-frozen-001.corrected-view.json  sha256 49a66122eee0eba7e50ef57835bea4f7b4fe0a7eda7a2a1fe5a0ddf542763e15
fields corrected (9):
  $.arms.primary.ambiguity_rule
  $.arms.primary.arm
  $.arms.primary.description
  $.arms.primary.status
  $.arms.secondary.ambiguity_rule
  $.arms.secondary.arm
  $.arms.secondary.description
  $.arms.secondary.status
  $.limitations[4]
authoritative        : false, see authority_note
```

The original manifest hash was verified unchanged immediately after the dry run.

The corrected view carries, at top level:

- `authoritative: false`
- `derived_from`, holding the original manifest path, its sha256, and its content hash
- `derivation_script`, holding the script path and the script's own sha256
- `corrected_fields`, the nine paths listed above
- `authority_note`, stating that the authoritative pair is the original manifest
  plus this erratum, that only arm declaration labels were changed, and that the
  frozen split was not re-read

The filename `p1-frozen-001.corrected-view.json` is deliberately distinct from
`p1-privacy-report.json` so the two cannot be confused in a directory listing or
a citation.

## 7. Effect on the approval

None of the six bound values changed:

| # | Bound value | State |
|---|---|---|
| 1 | `prompt_sha256` | unchanged |
| 2 | `adapter_version` and model identity | unchanged |
| 3 | `locator_version` and strategy | unchanged |
| 4 | Acceptance thresholds | unchanged from section 6 |
| 5 | Three split hashes | unchanged |
| 6 | Runtime configuration | unchanged |

The run recorded `frozen_config_asserted: true` with
`frozen_config_sha256 80333f1b3022f205fff238360a5a48884d7b73980e1f550af939fa8c22a1b069`,
and the 501 character approval record is present in `preregistration_approval`.
The frozen split was not touched.

The approval therefore stands. External auditor confirmation is pending and will
be recorded here when it arrives, including any instruction that changes the
handling proposed in section 8.

## 8. Publication rule

Demonstration material and the submission package use only the corrected,
amendment-aligned view. The raw manifest keeps its place in the evidence
directory, and a pointer to this erratum is placed alongside it so that anyone
reaching the raw file sees the correction before quoting a label from it.

The measured results are unchanged by this erratum and are stated here so the
correction cannot be mistaken for a change in outcome:

| Path | Combined | Turkish | English |
|---|---|---|---|
| Baseline recall | 0.7606 | 0.7556 | 0.7657 |
| `surface_exact_search`, primary under amendment 001 | **0.9782** | 0.9889 | 0.9676 |
| `model_offsets`, secondary | 0.7606 | 0.7556 | 0.7657 |
| Primary arm accepted payloads | 136 of 180 | 78 of 90 | 58 of 90 |
| Accepted escapes, every path | 0 | 0 | 0 |

Incremental against the deterministic baseline: `surface_exact_search` adds 470
true positives and 7 false positives; `model_offsets` adds 0 true positives and
903 false positives. Model status was `OK` on all 180 records. The mandatory
safety gate reports PASS.

## 9. What this erratum does not do

- It does not modify, amend, revert, or re-sign the original manifest, the
  checkpoint, or the logs.
- It does not re-read the frozen split or invoke the model.
- It does not change any threshold, any bound value, or the approval record.
- It does not claim the gate pointer was stale, because it was not.
