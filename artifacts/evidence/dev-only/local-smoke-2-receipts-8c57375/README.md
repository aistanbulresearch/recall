# LOCAL SMOKE ONLY — NOT THE FROZEN RUN — NOT SUBMISSION EVIDENCE

These files are the output of a two-case local smoke test run on 2026-08-27
while the receipt runner was still being developed. They were found sitting at
the canonical evidence path `artifacts/evidence/full-cohort-receipts/`, where
they could be mistaken for the real measurement, and were moved here for that
reason.

| | |
|---|---|
| Receipts | 2 |
| Posture | `local` |
| Code source commit | `8c57375ee0a3704885f4214790d1d27d2a23c480` |
| `privacy-receipts.json` sha256 | `899456f1c23bf33744a1da8681295ecff8a20332353431fc1d687b3e44475268` |

**This is not the frozen measurement.** The frozen full-cohort run is 462
receipts produced at commit `697aa6ebcf691f39b486f384b1d6a3f7f84eb8af` and
preserved, with its compatibility report, under
`artifacts/evidence/privacy/full-cohort-receipts-697aa6e/`.

Nothing in this directory may be referenced by the website, the demo, the
compatibility report, or any submission material. `checkpoint.jsonl` is process
state and was never evidence; it is retained here only so the smoke output stays
whole.
