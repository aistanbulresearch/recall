# Phase 1 Platform Smoke Plan

- Status: preregistered
- Date: 2026-08-15
- Tasks: RCL-104, RCL-105, RCL-107
- Owner: aistanbulresearch
- Data mode: `SYNTHETIC`

## Objective

Determine which Recall platform dependencies are actually installed, authenticated, enabled, authorized, callable, and safe to place on the critical path before product implementation begins.

## Boundaries

- Use no patient, clinical, repository, or private free-text data.
- Never print or persist access tokens, refresh tokens, credential JSON, billing-account IDs, project numbers, service-account keys, or raw IAM policy documents.
- Record project and account presence as booleans; keep resource identifiers out of committed reports unless they are purpose-created smoke resources.
- Do not mutate DNS, Hetzner, GitHub, production services, IAM policy, organization policy, or existing data.
- Create only explicitly named temporary smoke resources after read-only preflight passes.
- Verify the exact resource before cleanup; never use a wildcard delete.
- Product code and clinical logic are out of scope.

## Test levels

| Level | Meaning |
|---|---|
| `L0_LOCAL` | Required CLI or SDK is installed and can load locally. |
| `L1_AUTH` | A non-secret authenticated identity and configured project are present. |
| `L2_DISCOVERY` | The service API is discoverable and an authenticated read/list call returns a classified result. An empty list is valid; an unparsed error is not. |
| `L3_ROUNDTRIP` | A purpose-created temporary resource or request succeeds, is read back, and is cleaned up when safe. |
| `L4_RUNTIME` | A managed agent or model invocation returns a schema-checked synthetic response and its resource/revision is read back. |

## Result taxonomy

| Result | Definition |
|---|---|
| `PASS` | The target test level completed and independent read-back confirmed the mechanism. |
| `PARTIAL` | Lower levels passed, but the target level was not run or requires another dependency. |
| `BLOCKED_API_DISABLED` | Identity/project exist, but the required API is disabled. |
| `BLOCKED_PERMISSION` | Service is reachable but the active identity lacks the required permission. |
| `BLOCKED_BILLING` | Billing is absent or rejected. |
| `BLOCKED_ALLOWLIST_OR_PREVIEW` | Documentation exposes the feature but the account or region cannot access it. |
| `BLOCKED_REGION` | No tested supported region is usable without changing the architecture decision. |
| `UNAVAILABLE_LOCAL` | Required local CLI, SDK, binary, or model file is absent. |
| `FAIL` | The call succeeded superficially but schema, read-back, cleanup, or mechanism proof failed. |

## Preregistered component matrix

| Component | Target level | Cheapest discriminating test | Pass condition | Failure condition |
|---|---:|---|---|---|
| Google Cloud CLI | L0 | Version and component inventory | Version parsed, command exits zero | Missing or unusable CLI |
| User auth and ADC | L1 | Active-account presence and suppressed-token acquisition | Both identities usable without printing credentials | No active auth or ADC acquisition fails |
| Project and billing | L1 | Configured project plus billing-enabled boolean | Project configured and billing enabled | Missing project or billing disabled |
| Vertex Gemini | L4 | One synthetic strict-JSON generation request | HTTP success, expected JSON shape, latency recorded | Model unavailable, permission/billing error, invalid response |
| ADK and Agent Platform SDK | L0 | Import and version probe in an isolated environment | Required modules import and versions are recorded | Import/install failure |
| Agent Runtime | L2 then L4 | List reasoning engines; later deploy/invoke/read/delete one minimal agent | Authenticated list plus managed invocation and read-back | API, permission, deployment, invocation, or cleanup failure |
| Agent Registry | L2 then L3 | List registry components; later register/read/delete one smoke endpoint or agent | Discovery call plus exact resource roundtrip | Unsupported region, permission, or read-back failure |
| Memory Bank | L2 then L3 | Discover API; after runtime exists create/read/delete one synthetic operational memory | Memory roundtrip under the smoke runtime | Memory requires unavailable runtime or access is denied |
| Agent Identity | L2 | Verify documented identity type/API support without changing IAM | Capability visible and usable by the smoke runtime path | Preview/allowlist or permission block |
| Agent Gateway | L2 | Discover endpoint/API and available bindings without creating policy | Authenticated discovery succeeds | Feature absent, preview-gated, or permission denied |
| Model Armor | L2 then L3 | List templates; create one exact smoke template; sanitize benign and injection strings; delete template | Template read-back and both calls return parseable filter results | Disabled API, permission, regional endpoint, schema, or cleanup failure |
| Firestore | L2 | List databases only; do not create a database before region decision | Authenticated list returns parsed result | Permission/API failure |
| Pub/Sub | L3 | Create/read/delete one exact empty topic | Exact topic roundtrip and cleanup | Any create/read/delete mismatch |
| Cloud Run | L2 | List services in selected candidate region | Authenticated parsed list | API, region, or permission failure |
| Cloud Scheduler | L2 | List jobs in selected candidate region | Authenticated parsed list | API, region, or permission failure |
| Secret Manager | L3 | Create/read metadata/add dummy version/access/destroy exact temporary secret | Version content matches synthetic sentinel and resource is cleaned | Permission or read-back mismatch |
| Logging and Trace | L2 | Authenticated API discovery/list without raw trace export | APIs reachable and response parsed | API or permission failure |
| Local Gemma and llama.cpp | L0, later benchmark | Binary/model inventory without broad filesystem scan | Required binary and selected model path exist | Missing binary or model; benchmark does not start |

## Safe temporary resource contract

- Prefix: `recall-smoke-20260815-`
- Allowed temporary resources: one Pub/Sub topic, one Secret Manager secret, one Model Armor template, one Registry record, one staging bucket, and one minimal Agent Runtime resource only when their prerequisites pass.
- Dummy secret value: a fixed non-secret smoke sentinel.
- All created resource names are captured in process memory and matched exactly before cleanup.
- Existing resources are read-only and must never be deleted or modified.

## Measurements

- CLI/SDK availability: count and percentage of required local tools found.
- Auth readiness: user auth, ADC, project, and billing booleans.
- Service discovery: passed components divided by attempted components, with blocked reasons separated.
- Safe roundtrips: successful create/read/delete sequences divided by attempted sequences.
- Vertex request: model name, HTTP/result class, strict-JSON validity, and wall-clock latency.
- Agent Runtime request: deployment time, invocation time, schema validity, and cleanup result.
- Local Gemma preflight: binary presence, model presence, and startup eligibility. Full p50/p95 benchmark remains RCL-107 work after preflight.

## Decision rule

- `GEÇ`: Vertex Gemini, ADK/SDK, Agent Runtime, Agent Registry, Firestore, Pub/Sub, Cloud Run, Scheduler, Secret Manager, and sanitized telemetry have at least authenticated discovery; Runtime and Registry have a credible L3/L4 path with no unresolved billing or permission blocker.
- `YENİDEN TASARLA`: mandatory cloud primitives pass, but Runtime/Registry or regional governance requires a documented fallback or architecture change.
- `DUR`: identity, project, billing, Vertex Gemini, or another mandatory competition dependency cannot be made callable in the remaining schedule.

Memory Bank, Identity, Gateway, and Model Armor are reported separately. Their failure cannot be hidden, but it does not automatically stop the scientific authority path unless contest/category interpretation makes them mandatory.

## Evidence output

Write one sanitized report to `docs/evaluation/reports/2026-08-15--phase1-platform-smoke.md`. Log every material failed attempt in `docs/project/ERROR_LOG.md`. Do not mark RCL-104 or RCL-105 verified until the report proves their full acceptance criteria.
