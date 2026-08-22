# Local Model Selection — DUR-1 decision request

- Status: **decided by the owner on 2026-08-22** (lane L3 stop point 1 closed)
- Decision: `google/gemma-4-E4B-it-qat-q4_0-gguf`, Q4, Apache-2.0 licence confirmed by the owner
- Date: 2026-08-22
- Lane: L3
- Related: `corpus/PREREGISTRATION.md` section 8, protocol P1, RCL-107
- Prepared by: auditor, from public repository metadata only

This document recorded the candidates and the licence position so the owner
could decide. The owner decided on 2026-08-22: **`google/gemma-4-E4B-it-qat-q4_0-gguf`**,
with the Apache-2.0 licence independently confirmed. Sections 1 to 7 are the
evidence behind that decision and are kept unchanged. Sections 8 and 9 carry
what is still outstanding.

The model file itself has not been downloaded by this lane, and no key, token,
or credential is involved anywhere in this workflow.

## 1. What the model is actually for

The local model has exactly one job: propose character spans in a laboratory
note that the deterministic rule set may have missed. It returns strict JSON of
the form `{"spans": [{"start": int, "end": int, "identifier_class": str}]}` and
nothing else.

It never approves a span, never redacts, never decides egress, and never sees a
cloud endpoint. `src/recall/privacy/adjudicator.py` re-checks every proposal
against the note text deterministically, and `src/recall/privacy/gate.py` makes
the release decision without consulting it.

Since the structured-only egress profile landed, the demonstrated privacy claim
does not depend on the model at all: the cloud-bound payload declares no
free-text field, so a missed identifier has no field to travel in. The model is
now a measured bonus on the `SUMMARY_TEXT` comparator, not a load-bearing part
of the boundary. That lowers the cost of deciding this wrong in either
direction.

## 2. The licence position has changed since the brief was written

Brief L3 assumed a download would require the owner to accept the Gemma Terms of
Use. That is true of the Gemma 3 generation. It appears **not** to be true of the
current Gemma 4 official quantised builds.

Repository metadata read from the Hugging Face Hub on 2026-08-22:

| Repository | Declared licence | Downloads |
|---|---|---:|
| `google/gemma-4-E4B-it-qat-q4_0-gguf` | `apache-2.0` | ~799K |
| `google/gemma-4-12B-it-qat-q4_0-gguf` | `apache-2.0` | ~1.3M |
| `google/gemma-4-E2B-it-qat-q4_0-gguf` | `apache-2.0` | ~352K |
| `google/gemma-4-26B-A4B-it-qat-q4_0-gguf` | `apache-2.0` | ~350K |
| `google/gemma-4-31B-it-qat-q4_0-gguf` | `apache-2.0` | ~292K |
| `google/gemma-3-4b-it-qat-q4_0-gguf` | `gemma` | ~3.7K |
| `google/gemma-3-12b-it-qat-q4_0-gguf` | `gemma` | ~1.1K |

This is the licence each repository declares in its own metadata. It is not a
legal opinion, and it is not a substitute for reading the model card and any
notice shipped inside the repository. The owner should confirm on the model page
before downloading, because a click-through gate can exist independently of the
declared licence.

If the Apache-2.0 declaration holds, DUR-1 stops being a licence-acceptance
decision and becomes an ordinary dependency decision.

## 3. What this machine can run

Measured from the development host on 2026-08-22:

| Property | Value |
|---|---|
| Memory | 30.9 GB |
| CPU | Intel Core Ultra 7 255H, 16 cores |
| GPU | Integrated Intel graphics; no discrete accelerator |
| Free disk | 593.9 GB |

There is no discrete GPU, so inference runs on CPU, or on the integrated GPU
through a Vulkan or SYCL build of `llama.cpp`. Model size therefore buys quality
at a direct cost in wall-clock time, and the frozen P1 run has to process 180
notes inside one sitting.

The following are order-of-magnitude expectations for CPU inference, **not
measurements**. They exist only to size the decision, and the real numbers come
from the P1 run:

| Candidate | Approximate file size | Rough time per note | Rough time for 180 notes |
|---|---|---|---|
| `gemma-4-E4B-it-qat-q4_0` | ~4-5 GB | seconds | tens of minutes |
| `gemma-4-12B-it-qat-q4_0` | ~7-8 GB | tens of seconds | one to two hours |

## 4. Recommendation, and the decision taken

**Chosen: `google/gemma-4-E4B-it-qat-q4_0-gguf`** (owner, 2026-08-22).

- Apache-2.0 as declared, so no separate terms acceptance if that holds.
- Small enough to keep the privacy demo segment inside its 20-second slot and to
  finish the frozen 180-record run comfortably before the 08-28 freeze.
- Quantisation-aware training, so the int4 build is the intended artifact rather
  than a lossy afterthought.

**Fallback, only if the chosen model contributes no incremental true positive:**
`google/gemma-4-12B-it-qat-q4_0-gguf`. Same licence position, materially slower
on this hardware. Try it before removing the model from the demo, not after.
Switching to it is a different model identity and therefore a different P1 run
under preregistration conditions 4 and 5.

**Not recommended:** the Gemma 3 builds, because they carry the Gemma Terms and
buy nothing this task needs; and every community fine-tune in the search
results, because their provenance and licences vary and none of them is
necessary for a span-proposal task.

## 5. Known risk in the task itself

The model must return exact character offsets into a Turkish or English note.
Small instruction-tuned models are unreliable at character arithmetic, so the
realistic failure mode is not a hallucinated identifier but a correctly spotted
identifier at the wrong offsets.

That failure is contained rather than dangerous: the adjudicator verifies every
offset against the note text and drops proposals that do not line up, and the
outbound gate decides without the model. It does mean the incremental true
positive count may be low, and the preregistered rule already says that a model
which contributes nothing is removed from the demonstration.

## 6. Runtime, and one correction to the brief

The adapter talks HTTP to a laboratory-local `llama.cpp` server at
`/v1/chat/completions` using only the Python standard library. It needs the
`llama-server` binary on this machine and **no new Python dependency**.

Brief L3 asked for an `llama-cpp-python` pin recommendation to hand to lane L2.
There is nothing to pin: `pyproject.toml` and `uv.lock` do not need to change for
this lane.

## 7. Handling rules once a model is chosen

- The file lives under `models/`, which is git-ignored. It is never committed.
- The model runs on this machine only. Deploying it to any cloud runtime
  contradicts ADR-0004 and the data-sovereignty claim the segment is built on.
- No note text, corpus record, or laboratory prose is sent anywhere but the
  local server process.
- The exact repository, revision, and file name go into the P1 evidence manifest
  so the measurement is reproducible.

## 8. Outstanding items

| Item | Owner | State |
|---|---|---|
| Licence position confirmed as Apache-2.0 | owner | done, 2026-08-22 |
| Model choice: E4B, Q4 | owner | done, 2026-08-22 |
| Local runtime available: `llama-server` or an Ollama-served GGUF | owner | pending |
| Model file SHA-256 recorded in the P1 manifest | harness | computed automatically at run time from `--model-path` |
| Third-party register row updated | lane L2 (Codex) | requested, see section 9 |
| Frozen P1 run with the real model | lane L3 | blocked on the runtime |

The file hash is deliberately not written into this document by hand.
`scripts/privacy_eval.py` computes it from the file actually served and records
it in the evidence manifest, because a pasted hash is not evidence that this
file was the one measured. Preregistration condition 4 refuses a model-backed
run that lacks repository, revision, quantisation, and that computed hash.

Until the runtime exists, protocol P1 runs with the deterministic path and the
labelled oracle stub only, and no local-model claim is written anywhere.

## 9. Third-party register row requested from lane L2

`docs/governance/THIRD_PARTY_REGISTER.md` belongs to lane L2, so this lane does
not edit it. The existing `Gemma model artifacts` row still reads
`Custom Gemma Terms and Prohibited Use Policy`, which no longer describes the
artifact this project uses. Requested replacement:

| Component or source | Planned role | Terms class | Distribution mode | Current decision | Required condition |
|---|---|---|---|---|---|
| Gemma model artifacts: `google/gemma-4-E4B-it-qat-q4_0-gguf`, Q4 quantisation-aware build | Residual identifier span proposals inside the laboratory privacy boundary | Apache-2.0, as declared by the publishing repository and confirmed by the owner on 2026-08-22 | Separately downloaded local artifact; never committed, never containerised, never deployed to a cloud runtime | Approved for the local privacy lane | Record repository, revision, file name, and artifact SHA-256 in the P1 evidence manifest before any measurement; keep the file under the ignored `models/` directory; synthetic corpus only; no clinical or workflow decision; the model proposes spans and never approves, redacts, or releases anything. |

Two supporting facts for that row:

- the publisher is Google's own namespace, not a third-party mirror, which is
  what the register's exclusion of unverified mirrors is aimed at;
- the artifact hash is produced by the P1 harness rather than transcribed, and
  the manifest that carries it is the evidence the register should cite.

The `llama.cpp` row already covers the runtime, and its condition that the
runtime licence does not cover the weights still holds and still matters.
