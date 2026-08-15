# ADR-0003: Managed agent platform as a governed control plane

- Status: accepted
- Date: 2026-08-15
- Owners: aistanbulresearch
- Related tasks: RCL-104, RCL-605, RCL-606, RCL-607, RCL-608, RCL-610
- Supersedes:

## Context

The Fleet category requires more than several static agent classes. Recall must visibly prove cataloged institutional capabilities, managed execution, strict identity and tool scopes, and recoverable routing. Enterprise Agent Platform deployment is therefore part of the target architecture, subject to actual account, region, and preview access.

## Decision drivers

- dynamic but bounded capability discovery;
- separate identities and tool permissions;
- managed runtime and trace evidence;
- deterministic recovery when a managed component fails;
- no platform feature may become clinical authority.

## Options considered

1. Static in-process agents on one Cloud Run service. Simpler, but weak Fleet and separation proof.
2. Use every platform feature regardless of value. Rejected as bonus-driven scope inflation.
3. Use Agent Runtime and Registry on the critical path, then add Identity, Gateway, Memory Bank, and Model Armor only with explicit jobs and passed gates. Accepted.

## Decision

Deploy separately versioned agent revisions to Agent Runtime. Publish capability manifests to Agent Registry. Coordinator proposes a registry result; the deterministic Controller validates binding, version, identity, schema, health, and budget before invoking it.

Use Agent Identity and Gateway for least-privilege tool access when available. Managed component failure must yield a typed fallback or `ABSTAIN`; it must never widen permissions.

## Consequences

- Fleet discovery and governance become visible and auditable.
- Platform smoke tests and IAM design precede product implementation.
- Preview or regional limitations may reduce the managed feature set.
- The Controller remains more complex because it validates the control plane rather than trusting it.

## Failure modes

- stale or malicious Registry metadata;
- wrong agent version selected;
- identity has excessive permissions;
- Gateway bypass invokes an arbitrary endpoint;
- runtime unavailable or trace correlation missing.

## Verification and evidence

- Registry catalog read-back and selected-version receipt;
- separate runtime revision and service identity per role;
- allowed and denied tool-call tests;
- unavailable Registry/Runtime test;
- sanitized cross-service trace linked by run and artifact IDs.

## Rollback or supersession

If A2A, Gateway, or managed Identity is unavailable, use Controller-mediated invocation with pinned allowlisted endpoints and service accounts. If Runtime or Registry is unavailable, stop and reassess Fleet category viability before replacing the critical path.
