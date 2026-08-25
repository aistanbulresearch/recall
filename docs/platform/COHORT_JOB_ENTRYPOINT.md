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
`RECALL_EXPECTED_PROJECT_SHA256`, and `RECALL_COHORT_PREPARATION_SHA256`. The
last value for preparation bundle v1 is
`c460340e75bf186980c8e7a938c5c5e0b4da89599890b2864af7dabdb4ffe841`.
The job uses its service account through workload ADC. No user ADC, HMAC key,
or `RECALL_PRIVACY_SIGNING_KEY` may enter the image or job configuration.

Before each date, the owner/coordinator runs the lab-local preparation command
against that date's namespace. It installs only the exact committed synthetic
PrivacyReceipt, WatchCase, and replay-observation wires locked by the bundle.
The managed job revalidates the lock before creating ScanRuns. This proves
managed scheduling, not managed privacy admission.

Deployment verification without a second selection:

```text
python -m recall.scheduler.entrypoint --preview-date 2026-08-26
```

Preview validates the committed bundle, RCL-205 hashes, predictions, and
selection, returns `writes: 0`, and never constructs a ledger or cloud client.
