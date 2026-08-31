# Generation-27 terminal evidence export — provenance

This directory is a public, redacted export of one completed cohort execution.
It was produced by reading, never by running: no build, repoint, retry, cleanup,
submission or new execution was triggered, and nothing was written to Firestore
or Cloud Run at any point.

| | |
|---|---|
| Deployed source commit | `63437d20e493f09296af73f50348eb60fbe11030` |
| Deployed source tree | `0d04d0c572bc3b4dbaa77ead3bf3adbdaac00a78` |
| Deployed image digest | `sha256:ca4a789c12795b4d968be86a57bac26526e0d4430d3e4e158bc8a22191c8be2c` |
| Job generation | 27 (read from the Cloud Run execution's own `jobGeneration` label) |
| Export parser commit | `63437d20e493f09296af73f50348eb60fbe11030` — the production contract code of the deployed tree |
| Export produced (UTC) | 2026-08-31T15:01:38Z |
| Writes performed | 0 |

## How the run was identified

The recovery prefix was **not** discovered by scanning collections and **not**
assumed to be the most recent one. It comes from the immutable local launch
receipt for this attempt, and the exporter re-derives it from that receipt's own
plan hash and recovery attempt id before using it:

```
prefix = "dev_recall_final_p" + plan_sha256[:8] + "_c6_r" + sha256(recovery_attempt_id)[:10] + "_"
       = dev_recall_final_p8cb69fbd_c6_r7713b27758_
```

The derived value and the value stored in the receipt were compared; a mismatch
would have aborted the export.

The Cloud Run execution was identified the same way. The launch receipt records
the aliases of every execution that existed **before** this attempt; listing the
job's executions and removing that baseline left exactly one candidate, and its
`jobGeneration` label reads 27. Its raw execution name is never published — only
a deterministic alias derived from it.

## Read surfaces used

- Firestore REST `GET` on the five exact-prefix collections
  (`artifacts`, `watch_cases`, `scan_runs`, `scan_run_events`, `review_tasks`).
  Paginated GETs only: no structured-query POST, no write, update or delete
  endpoint appears anywhere in the exporter.
- `gcloud run jobs executions list` and the resulting resource description,
  read-only.
- The local immutable launch receipt under the operator's own home directory.

Every artifact was parsed with the deployed tree's production contract parser
and its producer registry before any figure in this export was computed.

## Redaction rules

- Case, run, artifact, invocation and trace identifiers are replaced by
  deterministic, non-reversible aliases: `sha256(salt : kind : id)[:10]` with a
  fixed export salt. The same identifier always yields the same alias, so the
  files cross-reference each other, and no alias can be turned back into an id.
- The Cloud Run execution name is replaced by `sha256(name)[:16]`, the same
  alias function the production launch tooling uses.
- Content hashes are **kept**. They are evidence anchors rather than
  identifiers, and they are what allows a reader to check a claim against the
  stored bytes.
- No prompt text, model output, reasoning content, tool payload or free-text
  detail field is exported anywhere.
- No project id, account, service-account name, endpoint id, credential or
  bearer token appears. The manifest's `delta` and `final_only_supersession`
  blocks carry raw run and artifact identifiers, so only their shapes are
  published.
- A scan over the produced files rejects any RFC-4122 identifier, any resource
  path prefix, any service-account domain, the project id, and any credential
  or bearer-token pattern. The export was regenerated until that scan reported
  clean, and the scan is deliberately strict enough that even this document
  avoids quoting the literal tokens it forbids.

## Files

| File | Contents |
|---|---|
| `cases.json` | 456 rows, one per scan run: aliases, terminal state, per-role completion, policy outcome and reason codes, receipt presence and hashes |
| `halted.json` | The eight technical terminals, each with the failed role, the agent receipt's technical code, the controller's failure receipt, the trace alias, and the closure checks |
| `cohort-summary.json` | Totals recomputed from the artifacts beside the run's declared telemetry, plus the governance checks |
| `execution-binding.json` | The execution alias, its generation label, the deployed commit/tree/image, start, end, duration and terminal state |
| `manifest.json` | The cohort day manifest's non-identifying fields, including its own `INCOMPLETE` status |
| `mode-summary.json` | Data-mode receipts by scope, and the explicit absence of a cohort-level receipt |
| `sample-chains.json` | Five artifact chains chosen deterministically by sorted alias |

## What this export does not establish

- **Actual billed cost.** The manifest carries a projection and reserves; its
  own `actual_billed_cost_state` reads `NOT_VERIFIED`, and no billing readback
  was performed. The projection is reported as a projection.
- **A cohort-level data-mode receipt.** None exists for this run. Its absence is
  reported; no hash is invented for it.
- **A completed cohort.** The Cloud Run execution succeeded, and the cohort day
  manifest's own status is `INCOMPLETE`. Both are reported, and the
  infrastructure result is never presented as the application result.
- **Anything about the eight halted cases beyond their receipts.** The recorded
  technical code is `agent_timeout` and the controller code is
  `controller_failed` with the stage named. Why those particular agent calls
  exceeded their deadline is not determined here.
