# Recall Handoff

## Read first

1. `AGENTS.md`
2. `docs/project/STATUS.md`
3. `docs/project/MASTER_PLAN.md`
4. `docs/project/OPERATING_PRINCIPLES.md`
5. `docs/architecture/TARGET_ARCHITECTURE.md`
6. `docs/governance/DEPENDENCY_LICENSE_POLICY.md`
7. `docs/governance/THIRD_PARTY_REGISTER.md`
8. `docs/demo/FOUR_MINUTE_STORYBOARD.md`
9. `docs/demo/WEB_INFORMATION_ARCHITECTURE.md`
10. `docs/demo/DERIVED_VALUE_REGISTRY.md`
11. `docs/security/THREAT_MODEL.md`
12. `docs/contracts/ARTIFACT_CONTRACTS.md`
13. `docs/contracts/LIFECYCLE_STATE_MACHINES.md`
14. `docs/policy/DETERMINISTIC_POLICY_SPEC.md`
15. `docs/evaluation/EVALUATION_PROTOCOLS.md`
16. `docs/evaluation/HISTORICAL_REPLAY_CASE.md`
17. `docs/evaluation/HISTORICAL_REPLAY_CANDIDATE_LEDGER.md`
18. `docs/evaluation/HISTORICAL_REPLAY_SOURCE_MANIFEST.json`
19. `docs/adr/ADR-0001-durable-watchcase-and-short-scan-runs.md` through `ADR-0007-policy-outcomes-and-technical-halt.md`
20. `docs/project/ERROR_LOG.md`
21. relevant evidence ledgers

## Current objective

Establish Recall as a prize-competitive hackathon project with a managed, auditable, privacy-preserving multi-agent critical path and a web experience built concurrently with the backend.

## Current state

- Date: 2026-08-16.
- Phase: Phase 0 verified; Phase 1 smoke is partial and stopped at billing selection; the Phase 2 design package is frozen and passed its local consistency audit.
- GitHub: `https://github.com/aistanbulresearch/recall`, private and initially empty.
- Local repository: `C:\Users\oacav\OneDrive\Desktop\recall project`.
- Product implementation: not started.
- No privacy, scientific, reliability, or production claim has been validated.
- Documentation baseline passed local structure, link, identity, ignore-rule, commit, push, and remote read-back checks.
- Google Cloud CLI, user auth, ADC, and five required SDK imports passed; no cloud resource was created.
- A dedicated Recall project is `ACTIVE` under the single organization; CLI and ADC target it.
- The project is billing-disabled. Two open billing accounts exist with no safe automatic organization/name match.
- Local Gemma runtime and model artifacts were not found in checked standard locations.
- RCL-101 is verified: owner eligibility and authority are confirmed, entry capacity is `individual/solo`, and no sensitive personal details are stored. A live Devpost recheck remains only as a final-submission control.
- RCL-102 is verified. The Rules require rights and license compliance but no special repository license; the owner approved Apache-2.0 and `LICENSE` is present.
- Current Google Cloud terms prohibit Generative AI Services for clinical purposes. The contest build is therefore a synthetic, non-clinical research prototype; future clinical deployment is blocked behind a separate terms and regulatory gate.
- Phase 3 cannot start until the Phase 2 package has been committed and pushed by `aistanbulresearch`, the owner has been notified that the GitHub auditor-agent gate is ready, and findings are triaged.
- RCL-207 and RCL-208 are verified design gates. The implementation must follow the 3:45 storyboard, single-screen evidence surface, and deterministic derived-value registry.
- RCL-201 through RCL-204 and RCL-206 are verified design gates. Threats, denied actions, contracts, lifecycle transitions, budgets, failure codes, deterministic policy, and evaluation protocols are frozen but not implemented.
- ADR-0007 separates technical `HALTED` from Policy Gate `ABSTAIN`, routes no-change through Policy Gate, and keeps privacy quarantine outside the cloud run lifecycle.
- RCL-205 is verified as a design gate. The frozen positive is BRCA2 `NM_000059.4:c.7522G>C`; the two same-gene negative controls test exact allele and source-scope matching. The 472-day public-source interval is case-specific, and no product detection claim exists yet.
- RCL-211 is in progress. The local Phase 2 audit passed, the package was pushed, and PR #2 is open. Remote login, commit authorship, and PR authorship read-back all resolve only to `aistanbulresearch`; external finding triage remains.

## Locked decisions

- Product name is Recall.
- The web demo is a first-class product entity and evolves with every vertical slice.
- The jury story begins with human workload, not genetics jargon.
- Safety is expressed as structural inability, not a claim that an agent is well behaved.
- Every displayed number is derived from an authoritative artifact.
- Missing data is unknown and must fail loudly where integrity is required.
- LLMs never hold classification, notification, or terminal workflow authority.
- Four roles are separated: Fleet Coordinator, Evidence Watcher, Evidence Assessor, Citation Auditor.
- A deterministic Workflow Controller owns routing enforcement and execution budgets.
- A deterministic Policy Gate owns terminal workflow outcomes.
- Controller uses technical `HALTED`, never a fabricated policy outcome, when trusted policy execution or ledger integrity is unavailable.
- Commit, push, tag, and PR ownership must resolve only to `aistanbulresearch`; no co-author trailers.
- Recall is implemented independently in this repository. Other codebases may inform abstract engineering patterns or failure-mode questions, but no code, tests, fixtures, schemas, prompts, configuration, UI, documentation, artifact, or history may be copied.
- Do not create a voluntary public `pre-existing work` section when no component is imported. Review the exact wording only if a binding rule or submission field explicitly asks about prior work, inspiration, or reuse.
- A durable `WatchCase` carries multi-week continuity; each `ScanRun` is short, bounded, idempotent, and independently auditable; `ReviewTask` has a separate human lifecycle.
- Firestore remains authoritative. ADK Sessions and Memory Bank are explicitly non-authoritative.
- Memory Bank is allowed only for admitted operational context with provenance, scope, TTL, contradiction checks, and retrieval receipts.
- Agent Runtime and Agent Registry are target critical-path components. Identity, Gateway, Memory Bank, and Model Armor require Phase 1 access and failure-behavior gates.
- Local Gemma proposes residual identifier spans; deterministic local logic approves redaction and egress. Model Armor screens untrusted cloud-side source content when feasible.
- All artifacts and surfaces declare `SYNTHETIC`, `CAPTURED_REPLAY`, `LIVE_PUBLIC`, or `MOCK`.
- The contest deployment is non-clinical and synthetic-only for institutional records. De-identification does not itself authorize clinical-purpose use.

## Immediate next step

Audit PR #2 and record every finding and disposition. Product implementation and merge must wait for external finding triage.

## Known blocker

The owner wrote `racall.aistanbulresearch.com` while the product and repository are `recall`. Do not create DNS, TLS, reverse-proxy, or application configuration until spelling is confirmed.

The dedicated Recall project is active, but two open billing accounts are available and neither has a safe automatic match. Do not enable APIs or create service smoke resources until the owner identifies the billing account.

## Operational notes

- GitHub CLI is authenticated as `aistanbulresearch` when run with permission to access its local config.
- An initial sandboxed `gh` preflight failed because the restricted process could not read the GitHub CLI config; the approved retry succeeded.
- Do not expose GitHub tokens, cloud credentials, SSH material, or Hetzner host details in logs or committed files.
- Domain creation remains an owner action when the deployment phase is reached.
- GitHub currently rejects repository rulesets for this private repository without Pro. Squash-only merge, automatic merged-branch deletion, PR branch updates, and Issues are enabled; direct-push avoidance is process-enforced until a ruleset can be activated.
- Cursor's GitHub integration added one unsolicited disabled-Bugbot upsell comment to PR #2. The exact comment was deleted and the PR is visibly clean. Recheck comments, reviews, checks, and commit actors after every push; if it recurs, stop and ask the owner to disable the Cursor integration for Recall.

## Stop conditions

Stop and report if:

- a contest rule or disclosure obligation is ambiguous;
- a required managed service is unavailable;
- a test passes without proving the target mechanism ran;
- a model output is about to become authoritative;
- a UI value cannot be traced to a typed artifact;
- real clinical data or a secret is found;
- a commit would use an identity other than `aistanbulresearch`.
