# Phase 1 Platform Smoke Report

- Date: 2026-08-15
- Plan: `docs/evaluation/PHASE1_PLATFORM_SMOKE_PLAN.md`
- Tasks: RCL-104, RCL-105, RCL-107
- Data mode: `SYNTHETIC`
- State: partial, dedicated project created, blocked at billing selection

## Executive result

The local tooling and authentication layers are usable. Google Cloud CLI, user authentication, Application Default Credentials, and five required Python SDK imports passed. A new dedicated Recall project was created under the single accessible organization and independently read back as `ACTIVE` with display name `Recall`. It is now the CLI target and ADC quota project.

Project-scoped service tests did not run because billing is not enabled. Two open billing accounts are accessible, and neither has a unique organization-parent or Recall/AIstanbul name match. Selecting one automatically would risk charging the wrong account. No product or patient data was used.

## Measurements

| Measure | Result | Evidence |
|---|---:|---|
| Google Cloud CLI | PASS | Version `580.0.0`; launcher read back after archive installation |
| User authentication | PASS | Active authenticated identity count: 1 |
| Application Default Credentials | PASS | Suppressed access-token acquisition exited zero |
| Dedicated Recall project | PASS | 1 created; `ACTIVE`, display name, organization parent, CLI target, and ADC quota-project read-back passed |
| Billing | BLOCKED | 0 linked; 2 open accounts, 0 safe organization/name matches |
| Required Python SDK imports | PASS | 5/5 imported in an isolated `uv` environment |
| Project-scoped service discovery | NOT RUN | 0 services attempted pending target-project selection |
| Safe resource roundtrips | NOT RUN | 0 create/read/delete sequences attempted |
| Local Gemma runtime | UNAVAILABLE_LOCAL | 0/3 checked runtime commands found on PATH |
| Local Gemma model | UNAVAILABLE_LOCAL | 0 GGUF files found in checked standard locations |

## SDK versions

| Package | Version | Import |
|---|---:|---|
| `google-cloud-aiplatform` | 1.164.0 | PASS |
| `google-adk` | 2.7.0 | PASS |
| `google-cloud-firestore` | 2.28.1 | PASS |
| `google-cloud-pubsub` | 2.39.1 | PASS |
| `google-cloud-secret-manager` | 2.30.0 | PASS |

The packages were resolved in an isolated `uv` environment. No dependency or product file was added to the repository.

## Component disposition

| Component group | Highest proven level | Result | Next discriminating test |
|---|---:|---|---|
| Google Cloud CLI | L0 | PASS | None |
| User auth and ADC | L1 | PASS | None |
| Project and billing | L1 incomplete | BLOCKED | Project passed; owner selects one of two open billing accounts |
| Vertex Gemini, Runtime, Registry, Memory, Identity, Gateway, Model Armor | Not tested | PARTIAL | Authenticated API discovery in the selected project |
| Firestore, Pub/Sub, Cloud Run, Scheduler, Secret Manager, Logging, Trace | Not tested | PARTIAL | Authenticated API discovery in the selected project |
| Local Gemma and llama.cpp/Ollama | L0 | UNAVAILABLE_LOCAL | Install/select an approved runtime and Gemma GGUF artifact before benchmarking |

## Fail-loud findings

1. A signed Google Cloud SDK Windows installer returned exit code zero but left no runnable CLI at the intended or standard locations. This was not counted as success.
2. The official SDK archive initially contained no Windows launcher until its non-interactive `install.bat` completed. Success was accepted only after `gcloud.cmd` read-back and a zero-exit version call.
3. A local environment-variable probe failed because the shell exposed duplicate case-insensitive keys. The retry used the process environment dictionary and returned no configured Gemma path.
4. Local Gemma is not "clean" or "ready". The runtime and model are absent, so RCL-107 cannot begin.
5. Cloud service availability is unknown, not failed and not passed. Project-scoped discovery was deliberately stopped before billing was attached.
6. The first billing-account count incorrectly reported one because PowerShell preserved the parsed JSON array as one nested object. A direct value query and corrected JSON parse proved there are two open accounts.
7. The new project remains billing-disabled. Neither accessible billing account has a unique organization-parent or Recall/AIstanbul name match, so automatic linkage is not defensible.

## Cost and mutation record

- Purpose-created cloud resources: 1 dedicated GCP project.
- Existing cloud resources modified: 0.
- Billable model or managed-runtime invocations: 0.
- Repository dependencies added: 0.
- Local additions: isolated Google Cloud CLI under the current user's local application data and transient `uv` cache entries.

## Decision

`YENIDEN TASARLA` is not justified yet, and `GEC` is not earned. The gate remains `DUR` at the billing-selection checkpoint because mandatory project-scoped evidence is absent. After the owner identifies the correct billing account by display name, link it, verify billing read-back, and continue with read-only API discovery before enabling services or creating the preregistered temporary resources.

## Official references used

- Google Cloud CLI Windows installation: <https://docs.cloud.google.com/sdk/docs/downloads-interactive>
- Agent Runtime ADK quickstart: <https://docs.cloud.google.com/gemini-enterprise-agent-platform/build/runtime/quickstart-adk>
- Agent Runtime deployment: <https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/runtime/deploy-an-agent>
- Agent Registry endpoint registration: <https://docs.cloud.google.com/agent-registry/register-endpoints>
- Memory Bank API quickstart: <https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank/api-quickstart>
- Model Armor prompt and response sanitization: <https://docs.cloud.google.com/model-armor/sanitize-prompts-responses>
