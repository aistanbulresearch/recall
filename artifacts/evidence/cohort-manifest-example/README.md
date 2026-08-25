# Cohort manifest contract example

The Day-2 manifest and mode receipt are deterministic in-memory `SYNTHETIC`
examples for UI and contract binding. The history receipt is a deterministic
typed projection of the committed Day-1 LIVE-infrastructure/SYNTHETIC-data
`first.json`; it preserves that classification and does not promote Day-1 to
managed execution. These files are not a Firestore execution record, Cloud Run
Job proof, Day-2 evidence, or a billing measurement. The live Day-2 manifest
must be produced on 2026-08-26 from its committed source revision.

The example manifest uses a deterministic synthetic image-identity sentinel;
it is not a deployed OCI digest and must never be cited as runtime evidence.
Live execution must replace it with L1's deployed `RECALL_IMAGE_DIGEST`.
