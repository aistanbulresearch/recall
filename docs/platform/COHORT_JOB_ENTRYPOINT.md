# Managed cohort job entrypoint contract

L1 owns every Cloud Run Job, Cloud Scheduler, image, IAM, and deployment file.
L2 provides only the importable command:

```text
python -m recall.scheduler.entrypoint
```

The daily schedule is `16:00 UTC`; a `09:00 UTC` trigger is rejected because
the committed cases are due at `15:00 UTC`. The real execution window is
`16:00:00Z` through `16:09:59Z`. Real mode derives the selected date from the
UTC clock and has no date override. Each date uses
`dev_recall_m2_cohort_YYYYMMDD_` and proves a date-isolated synthetic cohort-day
execution, not cross-day WatchCase continuity.

Required environment variables are `RECALL_SOURCE_COMMIT`,
`RECALL_IMAGE_DIGEST`, `RECALL_EXPECTED_PROJECT_SHA256`, and
`RECALL_COHORT_PREPARATION_SHA256`. `RECALL_SOURCE_COMMIT` must be 40-character
lowercase hexadecimal and exactly equal the preparation bundle's
`source_commit`; a mismatch fails with `source_commit_mismatch` before any
ledger is constructed. `RECALL_IMAGE_DIGEST` must be the deployed immutable
digest in lowercase `sha256:<64 hex>` form and is persisted in
`CohortDayManifest` 2.0.0. The
last value for preparation bundle v1 is
`c460340e75bf186980c8e7a938c5c5e0b4da89599890b2864af7dabdb4ffe841`.
The job uses its service account through workload ADC. No user ADC, HMAC key,
or `RECALL_PRIVACY_SIGNING_KEY` may enter the image or job configuration.

The image must also contain the exact committed Day-1 evidence blob at
`artifacts/evidence/day1-manual-20260825-a7f31c9d/first.json`. Its raw SHA-256
is `fa588a3eee9d8ac66c6629f8668a1e878cdda7586b256c99299eb0ce56283825`
and Git blob OID is `7d82b5158865284c00d89a20445c24db4bca518a`. Startup and preview fail
closed if the packaged bytes differ. L2 projects those bytes into a
deterministic `CohortHistoryReceipt 1.0.0`; preparation persists and reads
that receipt back before any WatchCase, ScanRun, or manifest write. The Day-2
manifest names the receipt in `input_artifact_ids` and derives the historical
entry exclusively from it.

Before each date, the owner/coordinator runs the lab-local preparation command
against that date's namespace. It installs only the exact committed synthetic
PrivacyReceipt, WatchCase, and replay-observation wires locked by the bundle.
The managed job revalidates the lock before creating ScanRuns. This proves
managed scheduling, not managed privacy admission.

Deployment verification without a second selection:

```text
python -m recall.scheduler.entrypoint --preview-date 2026-08-26
```

Preview validates the committed bundle, Day-1 evidence blob, RCL-205 hashes,
predictions, and selection, returns `writes: 0`, and never constructs a ledger
or cloud client. After this L2 commit, L1 must rebuild the image, verify the
packaged Day-1 blob hash, and repoint the Cloud Run Job to the new digest;
changing source alone does not change the deployed image.
