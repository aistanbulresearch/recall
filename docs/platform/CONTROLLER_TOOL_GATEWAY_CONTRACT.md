# Controller Tool Gateway Contract

Status: L2 implementation and deterministic local tests completed on 2026-08-24.
L1 evidence records the deployed Cloud Run gateway at revision
`recall-tool-gateway-00007-6tg` with `ingress=all`, IAM authentication, zero
public principals, three exact service-level role invokers, enumerated inherited
project-level invokers, and application-level authentication refusal. Managed
Agent Engine-to-gateway reachability remains `UNANSWERED`; the production
Firestore transaction chain remains `NOT_VERIFIED`.

## Trust boundary

Fleet Agent Engines have no Firestore role and never receive datastore or public
connector credentials. Each module-level FunctionTool in
`src/recall/agents/tools.py` calls this internal Controller gateway. The gateway
authenticates the engine service account, verifies a short-lived Controller-issued
run capability, writes `ToolAuthorizationReceipt`, and only then invokes the real
bounded backend.

The capability is opaque to the model and signed with HMAC-SHA256 using
`RECALL_TOOL_CAPABILITY_SECRET_B64` from Secret Manager. It binds role, case,
run, data mode, tool IDs, exact artifact IDs and schemas, replay stages, and
exact citation-refetch grants. The issuer derives every grant from an authorized
`EvidenceObservation`; callers cannot supply citation metadata. A `RefetchGrant`
separately binds the authoritative
ledger artifact's `source_artifact_content_hash` and the cited public source's
`content_hash`. That public-source hash is SHA-256 over canonical JSON containing
the PubMed ESummary `identifier`, `title`, and deterministic PubMed `locator`;
both frozen replay and live refetch use this same bounded representation. It is
not the raw frozen capture hash or an EFetch article hash. The Auditor supplies
only `claim_id`; it cannot supply or alter title, locator, identifier, hashes, or
data mode.

## HTTP contract

- Method/path: `POST /v1/tools/{tool_id}:invoke`
- Allowed `tool_id`: `evidence_connector`, `ledger_read`, `refetch_metadata`
- Transport: HTTPS only. The measured final Cloud Run posture is `ingress=all`
  with unauthenticated invocation disabled and IAM authentication required.
- Authentication: `Authorization: Bearer <Google ID token>`.
- ID-token audience: exact internal Controller service URL configured as
  `RECALL_TOOL_GATEWAY_AUDIENCE`.
- Perimeter truth: Cloud Run admits identities that hold invoke permission
  through service-level IAM or inherited project-level roles. Inherited
  project-level invokers exist, so the three service-level role principals are
  not an exclusive caller set. Application endpoint authentication enforces
  issuer, audience, principal/role, and Controller-issued capability before
  backend dispatch; public/unauthenticated invocation remains forbidden.
- Principal map: `RECALL_WATCHER_PRINCIPAL`, `RECALL_ASSESSOR_PRINCIPAL`, and
  `RECALL_AUDITOR_PRINCIPAL`. Verified token email must match capability role.

Request body has exactly these fields:

```json
{
  "protocol_version": "1.0",
  "request_id": "uuid",
  "capability": "opaque-signed-token",
  "arguments": {}
}
```

Argument shapes are closed:

```text
evidence_connector  {"stage": "stage-0|stage-1|stage-2"}
ledger_read         {"artifact_id": "uuid"}
refetch_metadata    {"claim_id": "non-empty string"}
```

Response body is capped at 64 KiB and has exactly the protocol/request ID,
`ALLOWED|DENIED`, persisted authorization receipt or null, bounded result or
null, and error or null. `refetch_metadata` uses `PubMedConnector.fetch` through
`RefetchAdapter`; source failure is a normal deterministic result with verdict
`UNAVAILABLE` and `refetched_source: null`. Receipt persistence failure returns
`DENIED` with no receipt and never runs the backend. If an allowed backend result
exceeds the response cap, the bounded 502 preserves its persisted `ALLOWED`
receipt, returns a null result, and is cached for exact retry.

`ToolGatewayAsgiApp` is the closed, dependency-free ASGI adapter. L1 supplies the
ASGI server process and instantiates it with `build_tool_gateway_from_environment`.

## Managed Agent Engine session handoff (blocking L1 acceptance)

Installed SDK contracts are:

```text
AdkApp.create_session(*, user_id, session_id=None, state=None, **kwargs)
AdkApp.async_create_session(*, user_id, session_id=None, state=None, **kwargs)
AdkApp.stream_query(*, message, user_id, session_id=None, run_config=None, **kwargs)
```

Before each role invocation, the Controller must create one engine session with
initial state `{"recall.tool_capability": token}` and then stream with that exact
`session_id`. For the current REST caller this is:

1. `POST .../reasoningEngines/{id}:query` with
   `{"class_method":"create_session","input":{"user_id":...,"session_id":...,"state":{"recall.tool_capability":token}}}`;
2. `POST .../reasoningEngines/{id}:streamQuery?alt=sse` with
   `{"class_method":"stream_query","input":{"message":...,"user_id":...,"session_id":...}}`.

L1 must add an exact-request test for both calls and a managed smoke proving
`ToolContext.state`, `ToolContext.invocation_id`, and `ToolContext.function_call_id`
reach the production callable. Passing case/run/tool grants in the prompt or in
agent-generated arguments is forbidden. Until this exact path is executed, the
managed gateway chain is `NOT_VERIFIED` and deployment must not be called M1 PASS.

## Controller image and environment

The image must include these exact frozen paths, preserving repository-relative
layout under one `RECALL_REPLAY_ROOT`:

```text
docs/evaluation/HISTORICAL_REPLAY_SOURCE_MANIFEST.json
artifacts/evidence/rcl-205/**
```

Set `RECALL_REPLAY_MANIFEST` to the manifest path. Startup requires manifest
SHA-256 `eb846f3a082fa4f0530caaf41bc7d67698cb3bcd1f0df54c3c2ba54af89437e8`,
then `ReplayConnector.verify_manifest()` verifies all ten capture hashes. Any
mismatch aborts startup before work.

Additional required environment: `RECALL_NCBI_TOOL`, `RECALL_NCBI_EMAIL`, the
gateway audience and three principals above, and the Secret Manager reference
for the base64 capability key. Agent images receive only
`RECALL_TOOL_GATEWAY_URL`, `RECALL_TOOL_GATEWAY_AUDIENCE`, and an optional bounded
timeout; they do not receive the signing key or connector credentials.

Production uses `FirestoreGatewayInvocationStore` collection
`tool_gateway_invocations`. Atomic reservation fixes the receipt timestamp;
completed retries return the cached byte-equivalent response and do not invoke
the backend again. A concurrent/incomplete reservation fails closed with 409.
The current policy is deliberately at-most-once: a crash after reservation leaves
the request `PENDING` and requires a new Controller invocation/capability rather
than risking duplicate public-source or ledger reads.

## L1 deployment acceptance

1. `ingress=all`, IAM authentication, and no public/unauthenticated principal
   read back from Cloud Run.
2. The service policy has the three exact role principals and no unexpected
   service-level invoker; inherited project-level invokers are enumerated and
   prevent an exclusivity claim.
3. Application endpoint authentication enforces issuer, audience,
   principal/role, and Controller-issued capability before backend dispatch.
4. Controller identity alone has Firestore access and the capability secret.
5. Startup hash gate passes inside the deployed image.
6. Wrong audience, issuer, principal, expired token, and missing auth fail before
   receipt/backend dispatch.
7. Managed session state reaches each FunctionTool, three real tools return
   non-echo results, and each call has one persisted receipt.
8. Exact request retry yields one receipt and no second backend invocation.
9. Cloud Trace and Firestore read-back use deterministic IDs, not list/search.
