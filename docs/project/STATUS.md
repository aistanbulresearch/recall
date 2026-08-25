# Recall Status

## 2026-08-25 managed Day-N implementation checkpoint

- Staged cohort expansion is committed at `c65ee3d55524caf1d2d9d697c9bff712e35bca82`: 12 SYNTHETIC cases, including the original Day-1 three unchanged, five RCL-205 hash-bound `CAPTURED_REPLAY` anchors, and committed predictions of 3/2/4 runs for 2026-08-26/27/28.
- The L2 Day-N implementation is committed locally at `367637b12e92eda0c2aa54c8bdc12af3adbfe99d`. It derives the selected date from the actual UTC clock, rejects frozen Day-1 recurrence, uses date-isolated collection prefixes, records actual execution time separately from logical schedule time, reconciles idempotent retries, and emits one strict `CohortDayManifest 1.0.0` plus a downstream `DataModeReceipt`.
- The importable L1 entrypoint is `python -m recall.scheduler.entrypoint`. Selection preview for 2026-08-26 returned three selected cases and `writes: 0` without constructing a ledger or cloud client. The committed preparation bundle SHA-256 is `c460340e75bf186980c8e7a938c5c5e0b4da89599890b2864af7dabdb4ffe841`; no HMAC key is supplied to the managed job.
- Verification: independent code review PASS (30/30 focused), Master Judge PASS, repository Python suite 692/692 with the four authorized LIVE Firestore/SYNTHETIC integration tests, web 48/48, and post-test `dev_recall_3e_*`/`dev_recall_m2_cohort_*` collection read-back count zero.
- Claim boundary: the date-isolated Day-N implementation and deterministic local tests are verified. Cloud Run Job/Scheduler/IAM deployment, workload-identity behavior, actual managed Day-2 execution, billing/cost evidence, and live Day-2 read-back remain `NOT VERIFIED`. Managed admission, cross-day WatchCase continuity, and terminal agent execution are not claimed. No `infra/**` file was changed by L2.

## 2026-08-25 governance reconciliation

- RCL-106 is `TERMINATED` by owner decision DEC-2026-08-25-044. The exposure was detected and contained on 2026-08-22; this is residual-risk acceptance, not a claim of technical remediation.
- Measured L1 gateway evidence records `ingress=all` with IAM authentication, inherited project-level invokers, and application authentication refusal. Endpoint issuer, audience, principal/role, and capability enforcement is implemented and deterministically tested; capability-bearing managed Agent Engine reachability remains `UNANSWERED`.
- Erratum 001 Revision 4 is append-only and corrects the historical word "signed": no cryptographic signature exists; integrity is an unkeyed SHA-256 `content_hash` plus Git commit provenance.
- `artifacts/evidence/L1_EVIDENCE_INDEX.md` is integrated byte-identically from L1 commit `3b45770` and keeps every evidence limitation explicit.

## 2026-08-25 Day-1 scheduler pre-run checkpoint

- Integrated product reference `c46d33499027b8a9a3edfc11c8b6aa654dc76852` remains the last four-suite GREEN base (core 241, platform 259, privacy 140, web 48).
- Minimal `DAY1_MANUAL` cohort scheduling is implemented locally with Controller-level PrivacyReceipt admission, ledger transaction revalidation, three fixed SYNTHETIC WatchCases, one due selection, and duplicate-trigger idempotency.
- Focused scheduler/admission tests pass 24/24 after final review fixes; bounded core passes 261/261; privacy passes 140/140; platform excluding the known process-spawning token file passes 234/234. The isolated token file again hung after its first test in this coordinator process tree and was interrupted; this is recorded in ERROR_LOG and is not reported as green.
- Live Day-1 cohort execution is PASS from source commit `14587ac5ab9fa854b4d9b0a2138dad81761bb756`: first trigger created exactly one ScanRun/RUN_CREATED event from one due case, two future cases were excluded, and the second trigger created zero new records while reusing the run. Both direct exits were 0; full read-back equality and an independent Firestore read-back passed.
- Evidence is retained at `artifacts/evidence/day1-manual-20260825-a7f31c9d/`; manifest SHA-256 is `c47bd52b0785032cb652202ca77f792c726658b8c74f772a624347280ff4a2de`. No managed recurring schedule or terminal agent execution claim is made.
- The earlier committed preflight against `ea95e5e` correctly blocked two stale test fixtures; replacement commit `14587ac` passed the live ledger suite 4/4 with direct exit 0 and all test prefixes cleaned to zero.

## Snapshot

| Field | Current truth |
|---|---|
| Updated | 2026-08-21 |
| Phase | 72-hour recovery: bounded P1 remediation plus owner-approved Phase 3 golden path; Phase 1 billing linkage remains separately protected |
| Overall state | Last passing external audit is c861; the published 46af successor has two bounded P1 findings. Their local remediation passes all six validator entrypoints, 88 exact aggregate mutations, five positive controls, and independent re-review, but still awaits owner-authorized publication. RCL-011 is `PARTIAL_FAIL_CLOSED / DEFERRED` with zero `MECHANISM_PROVED`, two `EXECUTED`, and seven unchanged `NOT VERIFIED`; local product implementation is authorized, while PR #2 merge awaits a fresh exact-head PASS. |
| Product code | Started; RCL-302, RCL-303, RCL-304, RCL-306, and RCL-308 are implemented and locally verified; RCL-309 now includes a locally verified date-isolated Day-N scheduler, while managed deployment and live Day-2 execution remain pending |
| Deployment | Not started |
| Scientific validation | Not performed |
| Clinical validation | Not performed |
| Demo surface | Storyboard, information architecture, and 52-field value-lineage design corrected and locally verified; implementation not started |
| GitHub | Private repository; PR #2 remains open and unmerged at published head `46afabfcc5716dde6f13e49d118a63b2beacc903`; its exact-head audit returned `FAIL` with two bounded P1 findings. c861 remains the last passing audited head. |
| Local checkout | Created at `C:\Users\oacav\OneDrive\Desktop\recall project` |

## Current external-gate state

```text
current_external_audit_head=46afabfcc5716dde6f13e49d118a63b2beacc903
current_external_audit_verdict=FAIL
audited_predecessor_head=877c78d06d9b78f3071d17c81232fbc4302f857e
rcl_211=VERIFIED
merge_gate=NO_GO
phase_3_gate=OWNER_APPROVED
external_re_review=REQUIRED
historical_external_pass_head=195422e4d762d68d38e2b7f531cc5b1cd059cdb7
```

```graphify-snapshot
snapshot_scope=POINT_IN_TIME
snapshot_timestamp=2026-08-19T04:45:37Z
graph_nodes=254
graph_edges=276
graph_communities=49
graph_concepts=140
manifest_sources=75/75
missing_sources=0
broken_endpoints=0
policy_gate_nodes=1
policy_gate_incident_edges=5
graph_sha256=973089FA8EF6F333843879D213D3E3C721079BAB5234B95549F1DEBB920245AE
report_sha256=7F49F479F74FBF2424D255D632AB038C4EFDB7BF25873C9D45181DF63CE45F96
report_build_commit=c8be1947
historical_snapshots=240/260/44/129;231/248/45/120;242/258/48/131@74/74
evidence_scope=NAVIGATION_AND_ARTIFACT_INTEGRITY_ONLY
scheduler_runtime=NOT_VERIFIED
```

## Completed

- Product name changed to **Recall**.
- GitHub repository `aistanbulresearch/recall` verified as private and initially empty.
- Local checkout created at the owner-specified path.
- Contest target architecture and guardrail direction were previously designed and are being normalized into Recall documentation.
- Owner supplied mandatory lessons, engineering principles, authorship constraints, hosting target, and documentation requirements.
- Initial living plan, documentation protocol, operating principles, and evidence-ledger structure drafted.
- Documentation baseline pushed and read back at `5336432a3e353261813443f41a217388b68d585d`; GitHub author and committer are `aistanbulresearch`.
- Recall Obsidian project memory bootstrapped and synthesized; local absolute paths remain Git-ignored.
- Owner approved the Fleet architecture direction on 2026-08-15.
- Target architecture now separates durable `WatchCase`, short `ScanRun`, and human `ReviewTask` lifecycles.
- ADR-0001 through ADR-0008 record the corrected Phase 2 baseline. The final external re-review passed at exact remote head `195422e4d762d68d38e2b7f531cc5b1cd059cdb7`; its evidence boundary remains design and frozen source-package verification, not product behavior.
- Phase 1 smoke plan was preregistered before execution.
- Google Cloud CLI, user authentication, ADC, and five required SDK imports passed local smoke checks.
- The initial pre-project smoke stage created zero cloud resources; the subsequent owner-authorized step created one dedicated project and no service resources.
- One dedicated Recall GCP project was created under the single organization and verified `ACTIVE`; CLI and ADC target it.
- Billing account selection is `OWNER_REPORTED_SELECTED` with display name exactly `My Billing Account`; no billing account ID is stored. Billing linkage, credit terms or expiry, permissions, API states, budgets or alerts, resource creation, model calls, and spending remain `NOT VERIFIED` and unauthorized pending separate owner approval.
- The owner accepted an independent-implementation boundary: abstract pattern inspection is allowed, but no prior-project component or artifact may be copied into Recall.
- A hash-pinned eligibility checklist was completed from the owner-supplied official Rules snapshot; project timing and independent-work boundary pass, subject to continuous provenance.
- Owner confirmed all personal eligibility requirements, no prohibited conflict, `individual/solo` entry capacity, and authority to use the `aistanbulresearch` identity and repository. RCL-101 is verified without storing sensitive personal details.
- RCL-102 is verified. The Rules snapshot imposes no special repository license; the owner approved Apache-2.0 and `LICENSE`, policy, register, and source notes are present.
- Current Google Cloud terms require the contest deployment to remain a non-clinical research prototype. Synthetic institutional data and approved public evidence are the only contest inputs; future clinical deployment is a separate gate.
- The required post-Phase-2 GitHub auditor checkpoint was completed; c861 is the last passing audited head. The later 46af findings block PR #2 merge until remediation and re-review, but the owner separately approved local Phase 3 implementation on 2026-08-21.
- RCL-207 is verified as a design gate: the video targets 3:45, includes a 75-second uninterrupted managed run, a combined citation/tool-denial fault run, visible Google Cloud proof, and explicit cut rules.
- RCL-208 is verified as a design gate: every planned result field has a source artifact/path, deterministic derivation, missing-data behavior, and required test. No UI implementation claim exists yet.
- RCL-201 is verified as a corrected design gate: the threat model includes deterministic candidate authority, memory parity, immutable citation failure, explicit provenance composition, and cursor-recovery activation tests.
- RCL-202 is verified as a corrected design gate: strict envelope and versioned payload contracts now align candidate routing, evaluated policy states, data-mode composition, WatchCase backlog/attention, examples, and UI paths. Executable schemas remain RCL-302.
- RCL-203 is verified as a corrected design gate: separate lifecycle tables now define exact cursor, pending-evidence, attention, scheduling, duplicate, and recovery behavior in addition to CAS/idempotency/lease rules and budgets.
- ADR-0007 corrects the original lifecycle sketch: privacy quarantine creates no cloud run, no-change still passes through Policy Gate, and technical `HALTED` is distinct from semantic `ABSTAIN`.
- RCL-204 is verified as a corrected design gate: deterministic candidate facts, evaluated states, outcome precedence, complete lexical reasons, memory exclusion, immutable material-claim failure, and transactional task protocol pass the scoped local audit.
- RCL-206 is verified as a corrected design gate: protocols cover candidate authority, memory byte/task parity, citation failure, mode composition, cursor recovery, UI integrity, managed-fleet activation, and offline replay integrity.
- RCL-205 is verified at frozen-source-package level under protocol 1.0.1: ten exact captures and 1,400,869 bytes verify offline; one exact XLSX row is found; corrected chronology/linkage passes; a mutated byte and capture-root path escape are rejected. Product replay is not implemented.
- The local Phase 2 audit passed its stated checks, but the external audit found material cross-document and replay-package gaps that those checks did not detect. The earlier package is not merge-ready.
- Phase 2 package commit `9ab9fa9a59aa92ce9cf9b4a9a6ca7e8e7446c4f4` was pushed and independently read back. Active GitHub login, GitHub author, GitHub committer, commit author, and commit committer all resolve to `aistanbulresearch`; the commit has no body, trailer, Git note, or prohibited authorship marker.
- PR #2 was opened from `feature/rcl-010-fleet-architecture` to `main` and independently read back. PR author and both included commit author names/logins resolve only to `aistanbulresearch`; PR title/body contain no prohibited authorship marker. The PR remains open and unmerged for external audit.
- An unsolicited `cursor[bot]` upsell comment appeared on PR #2. It was identified, deleted by exact comment ID, and logged as ERR-2026-08-16-040. Post-delete read-back shows zero visible comments, zero visible reviews, and zero non-owner or prohibited commit/PR authorship metadata.
- The read-only PR #2 audit returned `PASS WITH REQUIRED CHANGES`: no P0, eight P1, eleven P2, and eleven P3 findings. F-01 through F-08 are accepted and recorded in ADR-0008 and the external-audit triage report.
- The scoped ADR-0008 consistency audit passes F-01 through F-06 at document level: 11 policy rows are lexically ordered, 3 fenced JSON blocks and 71 JSON files parse, all 52 UI Field IDs are unique, all 21 UI artifact types have contracts, 22 local links resolve, and whitespace/secret scans are clean. No executable behavior is claimed.
- Protocol 1.0.1 passes F-07/F-08 at frozen-source-package level with zero-network clean verification, exact-row parsing, mutation rejection, and path-boundary rejection. This does not verify Recall product behavior or the 472-day metric operationally.
- The complete F-01 through F-08 follow-up audit passes within corrected-design and frozen-source-package boundaries. Evidence scripts parse, all declared captures verify, 11 policy rows remain ordered, 52 UI IDs and 21 artifact types reconcile, and JSON, link, whitespace, secret, and authorship-marker checks pass. No product behavior is claimed.
- Recall Graphify traversal is recovered through the mandatory no-stamp runner: query, explain, and path smoke checks complete without hanging. Raw Graphify traversal commands remain prohibited on this OneDrive checkout.
- Owner-side live verification confirmed that identical ClinVar printable requests can hash differently because `ncbi_phid` changes, and that GEO `GSE248438` is public from 2024-09-27 and currently links PMID `41957374`; the Nature paper PMID `39779848` independently names the same GEO accession.
- Owner-only remediation commit `9cfee55883fc67cc48e79745ae8d73e3e4a21b3a` was pushed and read back with only `aistanbulresearch` author, committer, and PR ownership metadata. Staged-tree and clean-clone verifier/harness checks pass; immediate and first delayed actor scans are clean.
- Eight findings across the first four reviews are remediated locally. The clean verifier reports 10 captures, 1,400,869 bytes, 7 source-derived chronology checks, 12 exact-ID semantic checks, 11 exact-ID rights checks, 1 exact-ID live-spec check, 1 declared live source, 1 parsed XLSX row, and 0 network calls. The expanded harness rejects byte, semantic, path, root, rights, live-runtime, duplicate-live, hash-role, and junction faults.
- The fifth read-only local auditor review returned `PASS` with no actionable findings and independently confirmed duplicate/cross-class source rejection and all prior remediations. This is not remote committed-state evidence.
- The historical Phase 2 exact-head GitHub auditor re-review at `195422e4d762d68d38e2b7f531cc5b1cd059cdb7` returned `PASS` with no actionable findings. PR body counts and evidence boundaries, owner-only author/committer/actor metadata, zero bot surfaces, PowerShell 5.1 parser checks, clean verifier, and the full fault harness passed against that historical exact remote head.
- Historical RCL-211 design-package review passed at `195422e4d762d68d38e2b7f531cc5b1cd059cdb7`. Later collaboration publications reopened the gate; external audits at predecessor `877c78d` and failed parent `c8be194` returned `FAIL` on successive evidence-integrity defects. `c86139048d1532c79ed190d0cc98ce2ad878414b` is the last passing audited head. The current published head `46afabfcc5716dde6f13e49d118a63b2beacc903` returned `FAIL`; RCL-211 is verified, Phase 3 is owner-approved, and PR #2 remains open and unmerged pending remediation and re-review.
- ADR-0009 and `$recall-collaboration` define a repo-scoped coordinator, Scout, Worker, Smart Worker, and read-only Master Judge with a three-thread spawned-agent cap, exclusive writer leases, stable-worktree gates, and owner-protected external actions.
- Collaboration structural validation and official skill validation pass. The Recall-root run proves no mechanism-level row. The fourth-spawn refusal and Worker/Smart file bytes and hashes were observed live, but the ignored run root was later removed and authoritative parent control-plane evidence was not retained. Only custom-profile discovery and Judge verdict formatting are `EXECUTED`; Worker write and six other mechanism/telemetry rows remain `NOT VERIFIED`. The reports and hashes are documentation, not independently inspectable raw artifact evidence, so the Runtime Judge's stronger `PASS` provenance assessment is not adopted.
- The first independent collaboration code review found a green-but-dead validator. Its false-pass classes and twelve control mutations, including hash-adjusted wrong/duplicate profile-name, report-classification promotion, displayed aggregate promotion, displayed count drift, thread-cap promotion, and Judge-effort promotion, are now rejected. Exact runtime evidence and remaining `NOT VERIFIED` boundaries are parsed from the sanitized smoke report.
- An earlier collaboration follow-up returned `PASS`, but later pre-push review superseded it with `FAIL`. Four code-review cycles closed earlier findings, owner-only publication reached `877c78d`, and that external audit failed on classification/state binding. The c8 parent then failed on transcript and Graphify wording. The c861 successor passed exact-head external audit; the bounded Recall-root runtime successor now retains seven fail-closed residuals, including Worker write and thread-cap behavior.
- The canonical `graphify-snapshot` block is dated point-in-time artifact evidence, never durable current truth. Its historical sequence preserves the earlier roots without promoting them. Future handoffs must use a new timestamp/hash/build-scoped block or execute the read-only gate for live values. The registered two-hour automation has standing authorization only for its fixed inspected scope; manual refresh and any scope change require new explicit authorization. No refresh was run for this reconciliation. Graph nodes remain navigation/design evidence, not runtime proof.
- The exact 20-file collaboration artifact passed final pre-publish Master Judge review, staged-tree checks, owner identity checks, secret scanning, and owner-only commit/push at checkpoint `980ec6f69b74ab96c7a59541ea914a7122b2bf26`. Local and remote checkpoint hashes matched; commit author, committer, and GitHub actor were only `aistanbulresearch`; commit body, trailers, and notes were empty; immediate PR comments, review comments, reviews, statuses, and check runs were zero.
- PR #2 now describes the collaboration validator, twelve-mutation harness, and explicit runtime evidence boundary. Owner/association and body read-back passed without a stale pre-collaboration gate.

## In progress

- Phase 1 access and security gates for the minimum Vertex AI, Firestore, Cloud Run, and Logging path. Local Gemma is `CUT / DEFERRED`.
- Project-scoped API discovery after separate owner approval and verified billing linkage; the display-name selection alone does not authorize or prove either step.
- RCL-209 and RCL-210 implementation-level IAM, retention, platform-access, and outage proofs remain pending.
- RCL-011: `PARTIAL_FAIL_CLOSED / DEFERRED`. Its zero/two/seven evidence matrix and all seven `NOT VERIFIED` rows remain unchanged; they no longer block local Recall product implementation.
- RCL-106: terminated by DEC-2026-08-25-044 after the owner accepted the residual risk; exposure detected and contained on 2026-08-22.
- Prize-fit preference remains Best Architectural Design, then Individual/Hobbyist, Fleet, and Honorable Mention; it is not a score or probability claim. The owner-approved active M1 execution path is Fleet-first as of 2026-08-23.
- The complete external-auditor action register is active planning input. All seven degree-oriented extensions remain planned behind their 2026-08-24 entrance/access/rule gates: scale funnel, Cloud Trace/fleet dashboard, accelerated Week 0/3/6, blog/social/bounded Gemma, Registry plus second consumer, IAM plus Model Armor, and Agent Runtime; `LIVE_PUBLIC` evidence is also retained. None may be removed without owner decision.
- `RunEvidenceManifest` is a coordinator proposal only and awaits owner approval; the auditor's run/revision/trace/mode/hash/count/latency evidence requirements remain mandatory independently.

## Blocked

- Final hostname configuration: `recall` versus the written `racall` spelling requires owner confirmation.
- No external deployment work should begin before access and security gates.
- Google Cloud billing: selection is `OWNER_REPORTED_SELECTED` for display name `My Billing Account`, with no account ID stored. Billing linkage and every operational billing/cloud state remain `NOT VERIFIED`; no linkage, API enablement, resource, model call, budget, alert, or spending action is authorized.
- Live cloud preflight in this coordinator shell is `NOT VERIFIED`: the `gcloud` launcher was not discoverable in `PATH` or the checked standard user locations. This is a launcher-availability failure, not evidence that billing or APIs are disabled.
- Local Gemma benchmark is `CUT / DEFERRED`; it is not a blocking golden-path task.
- PR #2 merge: c861 is the last passing audited head and current published 46af returned bounded P1 findings. Merge requires owner-published remediation, fresh exact-head re-review, and owner merge approval. Local Phase 3 implementation is already owner-approved; RCL-011 is deferred and does not block it. RCL-106 is terminated under the owner decision recorded in DEC-2026-08-25-044.
- GitHub commit/push: DEC-2026-08-18-032 records owner authorization only for the gated P1/P2 remediation successor and its read-only exact-head re-review. Prohibited authorship, bot recurrence, identity mismatch, or any failed gate stops publication.

## Not started

- Project-scoped platform discovery and temporary-resource roundtrip smoke tests.
- Product implementation and TDD.
- Privacy/evidence/reliability evaluation.
- Reviewer web application.
- Cloud Run deployment and hosted proof. Hetzner and custom DNS are `CUT / DEFERRED`.
- Demo recording and submission.

## Current risks

| Risk | Severity | Response |
|---|---|---|
| Domain-specific value may be unclear to the jury | High | Lead with specialist workload and show one visible action; minimize jargon. |
| Deep architecture may remain invisible | High | Map every control to a web state, trace, denial, or failure receipt. |
| Green tests may not exercise guardrails | High | Require activation counters and fault-injection evidence. |
| UI values may drift from backend artifacts | Critical | Maintain derived-value lineage and prohibit hand-entered result values. |
| Schedule may leave insufficient demo time | Critical | Build the web surface with each slice and freeze features on August 28. |
| Product name may have discoverability/confusion risk | Medium | Run naming-collision review before public launch. |
| Private repository plan does not permit branch rulesets | Medium | Use feature branches and PRs by process; enable protected-main ruleset immediately when the repo becomes public or the plan permits it. |
| Agent Registry or separate-identity capabilities may be preview-, region-, quota-, or account-limited | Critical | Timebox the authenticated Registry smoke to one day; retain Cloud Run plus the pinned Controller-validated manifest and separate-identity fallback. |
| Memory Bank scope could expand into evidence or policy authority | High | Limit the scheduled 2026-08-25 mini-brief to admitted operational hints plus enabled/disabled parity; Firestore remains authoritative and memory remains absent from policy inputs. |
| Current Google Cloud Generative AI terms prohibit clinical-purpose use | Critical | Keep the contest build synthetic and non-clinical; prohibit clinical-production claims; require a separate future contractual and regulatory gate. |
| Third-party license or data rights drift before release | High | Exact locks, SBOM, notices, model/data registers, unknown-license fail gate, and terms recheck at feature freeze. |
| A GitHub credential was rendered in a private subagent tool log | Closed | Exposure detected and contained on 2026-08-22. |
| Partial collaboration runtime evidence could be mistaken for full enforcement | High | Preserve the seven exact `NOT VERIFIED` residuals; require retained Worker-write evidence, authoritative thread-cap control-plane evidence, direct read-only denial, Smart runtime-profile telemetry, runtime effort telemetry, complete four-role tree retention, and authoritative protected-action ordering. |
| Frozen source package could be mistaken for product replay evidence | High | Keep RCL-503/RCL-506/RCL-801 unverified and label every source-package result as offline capture integrity only. |

## Next three actions

1. Obtain exact owner authorization to publish the independently reviewed bounded P1 remediation, then request a fresh exact-head audit without extending the validator into a general prose framework.
2. Begin RCL-301/RCL-302 and prove all three terminal outcomes with executable tests before Gemini integration, including F-09, F-11, F-14, mode badges, and `mode_set`; do not make the proposed `RunEvidenceManifest` a dependency without owner approval.
3. Restore a usable `gcloud` launcher, verify billing linkage, and obtain exact authorization for the four minimum APIs.
