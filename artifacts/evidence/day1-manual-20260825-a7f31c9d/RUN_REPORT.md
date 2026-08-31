# Day-1 Manual Cohort Run Report

- Status: PASS
- Data label: LIVE infrastructure, SYNTHETIC data
- Source commit: `14587ac5ab9fa854b4d9b0a2138dad81761bb756`
- Source tree: `30ec151f61850356bd42bf30c7e70af48083b3d6`
- Logical trigger: `2026-08-25T15:00:00Z` (`DAY1_MANUAL`)
- First execution: `2026-08-25T15:00:03.280432Z`, direct exit `0`
- Second execution: `2026-08-25T15:01:07.720049Z`, direct exit `0`
- Committed-source live Firestore gate: 4/4 PASS, direct exit `0`

## Prediction result

The committed prediction passed exactly: one ACTIVE due WatchCase produced one
CREATED ScanRun; two future WatchCases were excluded; the second identical
trigger created zero new ScanRuns and zero new events and reused the existing
run.

## Durable read-back

- Selected case: `b54d172c-d4c7-53d9-b6ea-a8ae154a84d3`
- Excluded cases: `b8390531-4c50-5f26-83da-0a1dadf07acf`, `6c0e023a-69de-57f3-8f0b-f1107ac7d1e4`
- Run ID: `37ec818b-719b-5dc2-8995-e85f1b67cfdf`
- Idempotency key: `dcf79ae7d46c3a2a1fb82d07d0b1e0d6768a1c594342f61647645c5d2081d11b`
- Event ID/code: `841bba4e-cd26-5cfc-a283-a0201c329d81` / `run_created`
- Counts after both triggers: artifacts 7; WatchCases 3; ScanRuns 1;
  ScanRunEvents 1; ReviewTasks 0.
- Full first/second read-back equality: true.
- Independent post-run Firestore read-back returned the same counts and IDs.

## Atomic checks

The ten shared checks all passed in both phases: live Firestore, expected project
hash, `(default)` database, three WatchCases, one selected due case, two future
exclusions, one total ScanRun, one RUN_CREATED event, zero ReviewTasks, and exact
collection counts. The phase-specific checks also passed: first trigger created
one; second trigger created zero and reused one.

## Evidence hashes

- `first.json`: `fa588a3eee9d8ac66c6629f8668a1e878cdda7586b256c99299eb0ce56283825`
- `second.json`: `ebd374d76bd2d89e7975f207c477e09b1fe6f9481ca771056f6b0879c05cbfec`
- `manifest.json`: `c47bd52b0785032cb652202ca77f792c726658b8c74f772a624347280ff4a2de`
- `manifest.json.sha256`: `f3c7d4d47f43342734b875864eca3deee045ae8d8a6a4aec0a0542a042a60c9a`

The manifest binds 104 committed runtime blobs to the source commit. Values
were written through the repository `redact_json` evidence path; a bounded
secret scan found no credential or private-key material.

## Inventory and claim boundary

- Cloud resource types created/deleted/remaining: 0/0/0.
- Firestore documents retained: 12 (7 + 3 + 1 + 1 + 0).
- Smoke/test prefixes were deleted in their own `finally` cleanup and read back
  as zero; the successful Day-1 evidence prefix is intentionally retained.
- Proved: working cohort selection and a durable Day-1 scheduling record.
- Not claimed: managed recurring scheduling or terminal agent execution.
- The local HMAC verifies the local run receipt only; it is not Cloud IAM or
  cloud-side authenticity evidence.
