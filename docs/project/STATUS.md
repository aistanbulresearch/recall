# Recall Status

## Snapshot

| Field | Current truth |
|---|---|
| Updated | 2026-08-17 |
| Phase | Phase 0 verified; Phase 1 blocked in part; Phase 2 F-01 through F-08 corrected and complete local follow-up passed |
| Overall state | Correction package is locally ready for safe owner-only push and external re-review; merge and Phase 3 remain `NO-GO`; product work not started |
| Product code | Not started |
| Deployment | Not started |
| Scientific validation | Not performed |
| Clinical validation | Not performed |
| Demo surface | Storyboard, information architecture, and 52-field value-lineage design corrected and locally verified; implementation not started |
| GitHub | Private repository; PR #2 remains open and unmerged at audited SHA `c4e2b02d`; correction work is local and unpushed |
| Local checkout | Created at `C:\Users\oacav\OneDrive\Desktop\recall project` |

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
- ADR-0001 through ADR-0007 record the Phase 2 baseline. ADR-0008 accepts the external-audit correction package; decisions 1 through 8 and replay protocol 1.0.1 are synchronized, and the complete local follow-up audit passes. External re-review remains pending.
- Phase 1 smoke plan was preregistered before execution.
- Google Cloud CLI, user authentication, ADC, and five required SDK imports passed local smoke checks.
- The initial pre-project smoke stage created zero cloud resources; the subsequent owner-authorized step created one dedicated project and no service resources.
- One dedicated Recall GCP project was created under the single organization and verified `ACTIVE`; CLI and ADC target it.
- The owner accepted an independent-implementation boundary: abstract pattern inspection is allowed, but no prior-project component or artifact may be copied into Recall.
- A hash-pinned eligibility checklist was completed from the owner-supplied official Rules snapshot; project timing and independent-work boundary pass, subject to continuous provenance.
- Owner confirmed all personal eligibility requirements, no prohibited conflict, `individual/solo` entry capacity, and authority to use the `aistanbulresearch` identity and repository. RCL-101 is verified without storing sensitive personal details.
- RCL-102 is verified. The Rules snapshot imposes no special repository license; the owner approved Apache-2.0 and `LICENSE`, policy, register, and source notes are present.
- Current Google Cloud terms require the contest deployment to remain a non-clinical research prototype. Synthetic institutional data and approved public evidence are the only contest inputs; future clinical deployment is a separate gate.
- A GitHub auditor-agent checkpoint is now mandatory after the Phase 2 package is committed and pushed and before Phase 3 implementation. The owner must be notified when that gate is ready.
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

## In progress

- Phase 1 access, security, and local Gemma feasibility gates.
- Project-scoped API discovery after the owner selects the correct billing account.
- RCL-209 and RCL-210 implementation-level IAM, retention, platform-access, and outage proofs remain pending.
- RCL-211 correction work: local follow-up is complete; await owner confirmation that Cursor integration is disabled, then run attribution preflight, owner-only push/read-back, and auditor re-review.

## Blocked

- Final hostname configuration: `recall` versus the written `racall` spelling requires owner confirmation.
- No external deployment work should begin before access and security gates.
- Google Cloud billing: the dedicated Recall project is active but billing-disabled; two open billing accounts have no safe automatic match, so owner selection is required.
- Local Gemma benchmark: no checked runtime command or GGUF model is installed.
- Phase 3 and merge: blocked until the corrected remote package receives auditor re-review and findings are closed.
- GitHub push: blocked until the owner confirms the recurring Cursor integration is disabled for Recall.

## Not started

- Project-scoped platform discovery and temporary-resource roundtrip smoke tests.
- Product implementation and TDD.
- Privacy/evidence/reliability evaluation.
- Reviewer web application.
- Hetzner deployment and DNS.
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
| Managed Agent Platform components may be preview-, region-, quota-, or account-limited | Critical | Run component-level authenticated smoke tests before product logic; record exact fallback or category impact. |
| Memory Bank could contaminate later runs with stale or poisoned context | High | Keep Firestore authoritative; enforce admission, scope, TTL, provenance, contradiction, and disabled-memory parity tests. |
| Current Google Cloud Generative AI terms prohibit clinical-purpose use | Critical | Keep the contest build synthetic and non-clinical; prohibit clinical-production claims; require a separate future contractual and regulatory gate. |
| Third-party license or data rights drift before release | High | Exact locks, SBOM, notices, model/data registers, unknown-license fail gate, and terms recheck at feature freeze. |
| Corrected F-01 through F-08 package has not yet received external follow-up review | High | Keep implementation blocked until safe owner-only push/read-back and auditor re-review pass. |
| Frozen source package could be mistaken for product replay evidence | High | Keep RCL-503/RCL-506/RCL-801 unverified and label every source-package result as offline capture integrity only. |

## Next three actions

1. Obtain explicit owner confirmation that the Cursor GitHub integration is disabled for Recall.
2. Run attribution preflight, owner-only commit/push, remote read-back, and visible actor scan, then request GitHub auditor re-review.
3. Review all 27 scheduled/cleanup findings against their affected future tasks so none silently disappear.
