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

- product source commit `29a833c30e16d70edccadbe10d574769f542787e`;
- `artifacts/evidence/cohort-compression/COMPRESSED_PREDICTION_PLAN_V2.json`,
  SHA-256 `05e61f4bbe3d6bb7540ecae310e3c6f9423dcae3a7933db59ef4267e84fd9226`;
- `artifacts/evidence/cohort-compression/preparation-bundle-v2.json`, SHA-256
  `4487e4d3e5973e0e714348f1d420a9328046ed1ba49f5c1a0478e9f174b90d04`.

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
has its own cycle identity, prefix, schedule epoch, and declared UTC window.
The runtime clock must fall in exactly one window. Zero or multiple matches
fail closed, and no runtime window override exists.

c1-c5 have committed predictions 3/2/4/1/1. c6 has 450 prepared onboarding
cases, but L1 must not create its trigger until the exact c1-c5 manifests and
authoritative ScanRun counts produce a content-addressed
`CohortHeadroomReceipt` whose decision is `PASS`. `DENIED`, missing, or
mismatched headroom blocks c6 writes.

## Preparation and zero-write preflight

Every session prefix must be prepared with the current product image, including
`CohortHistoryReceipt` persistence and read-back. Old seed data is not
compatible with a new image merely because the namespace exists.

Before c1, run this through Cloud Run Job execution under the same image,
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

Compressed execution emits `CohortDayManifest 3.0.0`; it does not relax or
rewrite historical 2.1.0. The compressed contract adds cycle identity/index,
plan version/hash, logical cohort due date, declared window, actual execution
time, `schedule_mode`, and `headroom_receipt_id`. Historical rows retain their
own `trigger_code` and `scheduled_for` and are validated under the rules of the
version that produced each row.

L3 must acknowledge compatibility against exact product commit
`29a833c30e16d70edccadbe10d574769f542787e` before L1 executes the compressed
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
