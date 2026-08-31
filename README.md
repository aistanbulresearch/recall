# Recall

Recall is a non-clinical research prototype that monitors approved public evidence for synthetic watch cases and prepares an auditable, clinician-reviewed workflow; it never classifies patients, edits clinical reports, or contacts patients.

## Why this architecture

Evidence monitoring is a multi-agent problem because discovery, interpretation, and citation verification have different failure modes and must not share authority. Recall therefore uses a deterministic Controller to own state, budgets, leases, retries, and policy, while three narrowly scoped roles remain separate:

1. **Evidence Watcher** reads allowlisted sources and produces typed observations and snapshots.
2. **Evidence Assessor** interprets a deterministic candidate receipt and proposes an evidence delta, including uncertainty and counter-evidence.
3. **Citation Auditor** independently refetches metadata and verifies material claim/source relationships.

Only the deterministic Policy Gate can emit `NO_ACTION`, `ABSTAIN`, or `REVIEW_REQUIRED`; a technical failure is `HALTED`. Model output and memory are non-authoritative.

## Architecture and data flow

```text
accepted PrivacyReceipt
        -> durable WatchCase / bounded ScanRun
        -> Controller -> Watcher -> Assessor -> Citation Auditor
        -> typed receipts and Evidence Ledger
        -> deterministic Policy Gate
        -> NO_ACTION | ABSTAIN | simulated REVIEW_REQUIRED task
```

The authoritative design and contracts are [`Target Architecture`](docs/architecture/TARGET_ARCHITECTURE.md), [`Artifact Contracts`](docs/contracts/ARTIFACT_CONTRACTS.md), [`Lifecycle State Machines`](docs/contracts/LIFECYCLE_STATE_MACHINES.md), [`Deterministic Policy Spec`](docs/policy/DETERMINISTIC_POLICY_SPEC.md), and [`Threat Model`](docs/security/THREAT_MODEL.md). The managed entrypoint and its zero-write preflight are documented in [`COHORT_JOB_ENTRYPOINT`](docs/platform/COHORT_JOB_ENTRYPOINT.md).

## Quick start

The first success is local and deterministic; it requires no Google Cloud credentials or network calls after dependencies are installed.
From a fresh clone checked out as `recall/`:

Prerequisites: Git, Python `>=3.12`, `uv`, Node.js, and Corepack (providing pnpm `11.19.0`).

```text
cd recall
uv sync --frozen
uv run --frozen pytest -q -p no:cacheprovider tests/contracts/test_canonical.py
uv run --frozen python scripts/run_fixture.py --fixture tests/fixtures/audited_change.json --backend memory
corepack enable
pnpm install --frozen-lockfile
pnpm --dir web test
pnpm --dir web dev
```

Open the local Vite address printed by the last command. It renders committed, artifact-derived evidence; there is no hosted URL in this repository. The Python project declares Python `>=3.12` in [`pyproject.toml`](pyproject.toml) and uses `uv.lock`; the workspace declares pnpm `11.19.0` in [`package.json`](package.json).

Useful web commands from the repository root:

```text
pnpm --dir web test
pnpm --dir web run web:build
pnpm --dir web dev
```

The two listed Python commands are bounded, deterministic, and use the in-memory backend; they do not create cloud resources. Cloud-dependent tests are not part of the quick start.

## Evidence map

- [`Generation-27 export`](artifacts/evidence/generation-27-export/) — redacted terminal export, provenance, manifest, execution binding, mode summary, and checksums.
- [`Generation-27 provenance`](artifacts/evidence/generation-27-export/EXPORT_PROVENANCE.md) — read-only export method and limitations.
- [`Frozen 462-receipt privacy evidence`](artifacts/evidence/privacy/full-cohort-receipts-697aa6e/) — byte-preserved privacy receipts and compatibility report.
- [`Claim Evidence Ledger`](docs/evidence/CLAIM_EVIDENCE_LEDGER.md) — approved wording and evidence boundaries.
- [`Demo Evidence Log`](docs/evidence/DEMO_EVIDENCE_LOG.md) — what may be shown and what remains planned.
- [`Architecture diagram draft`](docs/demo/ARCHITECTURE_DIAGRAM_DRAFT.md) and [`four-minute storyboard`](docs/demo/FOUR_MINUTE_STORYBOARD.md) — judge-facing product flow and demo context.

The two evidence populations have different denominators and must not be combined. All examples are synthetic institutional records or source-attributed public evidence.

## Current runtime status (honest boundary)

The retained Generation-27 export records Cloud Run infrastructure as **SUCCEEDED** and all **456** ScanRuns as terminal. It records **446** complete audits and **448** policy-bound outcomes: **445 `NO_ACTION` + 3 `ABSTAIN`**. The remaining **8** are technical `HALTED` cases. The retained final-audit artifacts were parsed and validated by the production contract path; the canonical cohort manifest is explicitly `INCOMPLETE`.

The latest source fixes are locally tested and classified **MECHANISM_PROVED**. A new live positive smoke is **NOT VERIFIED**. These statements do not claim a successful current deployment, billing result, hosted demo, or a completed cohort-level receipt.

## Optional Google Cloud path

Deployment and managed execution are owner-controlled and optional for local evaluation. Read the [`managed entrypoint contract`](docs/platform/COHORT_JOB_ENTRYPOINT.md), [`Cloud Run image definition`](infra/cohort-job/Dockerfile), [`Cloud Build definition`](infra/cohort-job/cloudbuild.yaml), and [`deployment tooling`](infra/scripts/deploy_fleet.py) before any authorized operation. The repository's evidence export is the safe read-only reference; do not infer a new run from it or start a 456-case execution from this README.

## Security and governance

- The laboratory boundary performs minimization, deterministic identifier detection, local residual-span detection, redaction, and an outbound scan before any cloud-bound payload.
- Firestore is the authoritative workflow/evidence ledger. Agents cannot write authoritative state or choose policy outcomes.
- Every role has a separate tool allowlist, identity, schema, budget, deadline, and forbidden-action checks. Tool authorization and failure receipts are retained as typed artifacts.
- Synthetic and public replay data are labeled at every surface. No real patient data, credentials, prompts, chain-of-thought, or raw identifiers belong in this repository.
- The [`Dependency and license policy`](docs/governance/DEPENDENCY_LICENSE_POLICY.md), [`Evidence Discipline`](docs/governance/EVIDENCE_DISCIPLINE.md), and [`Threat Model`](docs/security/THREAT_MODEL.md) define review and disclosure rules.

Recall is not a clinical device, does not provide medical advice, and makes no clinical-performance, privacy-accuracy, regulatory, or production-readiness claim.

## Reproducibility and evidence language

- **EXECUTED** — a bounded action has direct, retained output (for example, a local test or read-only export).
- **MECHANISM_PROVED** — source behavior is covered by deterministic tests and independent review; deployment or live-provider behavior is not implied.
- **NOT VERIFIED** — required runtime, cloud, billing, or external evidence is absent; it must not be presented as success.

Every displayed number must be derived from the committed artifact behind it. Historical, synthetic, replayed, cached, and mocked data cannot be generalized into clinical accuracy or safety claims.

## Contributing and license

Read [`AGENTS.md`](AGENTS.md), [`CONTRIBUTING.md`](CONTRIBUTING.md), and the project [`status`](docs/project/STATUS.md) before proposing a change. Use the repository's tests-first, evidence-led workflow and Conventional Commits. Recall is licensed under [`Apache License 2.0`](LICENSE).
