# Local Model Selection — DUR-1 decision request

- Status: **awaiting owner decision** (lane L3 stop point 1)
- Date: 2026-08-22
- Lane: L3
- Related: `corpus/PREREGISTRATION.md` section 8, protocol P1, RCL-107
- Prepared by: auditor, from public repository metadata only

Nothing has been downloaded. No licence has been accepted. This document exists
so the owner can make one decision with the facts in front of them.

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

## 4. Recommendation

**Primary: `google/gemma-4-E4B-it-qat-q4_0-gguf`.**

- Apache-2.0 as declared, so no separate terms acceptance if that holds.
- Small enough to keep the privacy demo segment inside its 20-second slot and to
  finish the frozen 180-record run comfortably before the 08-28 freeze.
- Quantisation-aware training, so the int4 build is the intended artifact rather
  than a lossy afterthought.

**Fallback, only if the primary contributes no incremental true positive:**
`google/gemma-4-12B-it-qat-q4_0-gguf`. Same licence position, materially slower
on this hardware. Try it before removing the model from the demo, not after.

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

## 8. What the owner needs to decide

1. Confirm the licence position on `google/gemma-4-E4B-it-qat-q4_0-gguf`, or
   accept the Gemma Terms instead if a Gemma 3 build is preferred for a reason
   not visible here.
2. Authorise the download of that one repository to this machine.
3. Confirm the fallback: if the primary contributes nothing measurable, try the
   12B build once, then drop the model from the demonstration.

Until step 2 happens, protocol P1 runs with the deterministic path and the
labelled oracle stub only, and no local-model claim is written anywhere.
