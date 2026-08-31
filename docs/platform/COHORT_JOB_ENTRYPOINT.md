# Managed cohort job entrypoint contract

L1 owns every Cloud Run Job, Cloud Scheduler trigger, image, IAM binding, and
deployment file. L2 provides the importable command only:

```text
python -m recall.scheduler.entrypoint
```

## Required mode and immutable inputs

Compressed execution requires `RECALL_SCHEDULER_MODE=COMPRESSED_V3`. Absence or
any other value fails closed. Historical date-aware execution is available only
with explicit `RECALL_SCHEDULER_MODE=LEGACY_DAYN`; there is no implicit fallback.

The compressed image must package these exact committed inputs:

- product source commit `b5cd5a815baad5980a3d62bfb49ab980b63e3057`;
- `artifacts/evidence/cohort-compression/COMPRESSED_PREDICTION_PLAN_V2.json`,
  SHA-256 `4c2b5ededcf79472781d0d58eca23b46278dcd0a9cc3fcaeb8c307f7a6c84e89`;
- `artifacts/evidence/cohort-compression/preparation-bundle-v2.json`, SHA-256
  `4b494be9c82de3c3762ecc6249169b26922334f6e47af0010dafb163667a5f57`.

`RECALL_SOURCE_COMMIT` must be lowercase 40-hex and equal both the product
source and bundle provenance. `RECALL_IMAGE_DIGEST` must be the deployed
immutable lowercase `sha256:<64 hex>` digest. The existing project and
preparation hash environment gates remain mandatory. Any disagreement stops
before a scheduler write.

The job uses its scheduler service account through workload ADC. No user ADC,
HMAC key, or `RECALL_PRIVACY_SIGNING_KEY` may enter the image or job. The Cloud
Run Job timeout is 1200 seconds. Only scheduler-SA may invoke the job.

## Plan-derived triggers

`COMPRESSED_PREDICTION_PLAN_V2` is the sole timing and prediction source. L1
must parse that committed file to instantiate the one-shot Cloud Scheduler
triggers; hand-selected or separately copied times are prohibited. Each trigger
has its own cycle identity, plan-isolated prefix, schedule epoch, and declared
UTC window. The prefix is
`dev_recall_m2_compressed_p<first-12-plan-sha>_<cycle>_<logical-date>_`;
never reuse an abandoned unscoped prefix.
Plan 4 declares c2's predecessor as the immutable plan-3 c1 prefix, plan hash,
and manifest ID. L1 must not copy c1 into the plan-4 namespace. c3-c6 resolve
their predecessor from the current plan namespace. Any missing or mismatched
declared predecessor fails before current-cycle writes.
The runtime clock must fall in exactly one trigger-start window. Zero or
multiple matches fail closed, and no runtime window override exists. The plan
also declares separate write and agent phase budgets plus one authoritative
end-to-end timeout; completion authority is not inferred from `window_end`.

c1-c5 have committed predictions 3/2/4/1/1. c6 has 450 prepared onboarding
cases, but L1 must not create its trigger until the exact c1-c5 manifests and
authoritative ScanRun counts produce a content-addressed
`CohortHeadroomReceipt` whose decision is `PASS`. `DENIED`, missing, or
mismatched headroom blocks c6 writes.
Plan 4 marks c6 `FIRESTORE_BATCH_V1`; the current Task-1 image refuses c6
before ledger construction. L1 must not create the c6 trigger until the
separately reviewed batching implementation is merged and deployed.

## Preparation and zero-write preflight

Every unexecuted session prefix must be prepared with the current product image, including
`CohortHistoryReceipt` persistence and read-back. Old seed data is not
compatible with a new image merely because the namespace exists.

Before each remaining cycle, run this through Cloud Run Job execution under the same image,
service account, environment, and prefix that the trigger will use:

```text
python -m recall.scheduler.entrypoint --verify-prefix YYYYMMDD
```

The command constructs the configured ledger, verifies the complete prepared
prefix, performs zero writes, prints a JSON result, and exits 0/1. Run it for
every session prefix. Any nonzero result blocks the whole session. The older
selection preview is not a substitute because it does not prove ledger
preparation read-back.

## Manifest and UI compatibility gate

FULL_AUDIT compressed execution emits `CohortDayManifest 3.3.0`; it does not
relax or rewrite historical versions. In addition to cycle and execution
evidence, the contract binds the durable batch-attempt receipt, exact recovery
parity, and separate trigger/write/agent/end-to-end timestamps. Historical rows
retain their own `trigger_code`, `scheduled_for`, and source schema and are
validated under the rules of the version that produced each row. The UI must
evaluate completion against
`$.deadline_policy.authoritative_end_to_end_deadline`, not `window_end`.

L3 must acknowledge compatibility against exact product commit
`2d8bebbe97794865f77f037dea518a39e8f75e38` before L1 executes the compressed
image. The visible label must be derived from manifest `schedule_mode`; copied
component text is prohibited. Intermediate manifests remain in the evidence
directory. Only the final manifest may enter the demo bundle.

## Evidence and claim boundary

For every cycle, retain `cycle_id | prediction | observation | run IDs | event
count | idempotency`, exact source/image/plan/bundle hashes, trigger identity,
real UTC timestamps, direct exits, prefix read-back, and inventory/cost
reconciliation. After deployment freeze, retain one verification tick against
that exact immutable revision.

Local implementation and deterministic tests are verified. Cloud deployment,
workload identity, prefix preflight, Scheduler triggers, Firestore execution,
c1-c6 observations, c6 headroom authorization, billing, final UI binding, and
the post-freeze tick remain `NOT VERIFIED` until their exact artifacts exist.
