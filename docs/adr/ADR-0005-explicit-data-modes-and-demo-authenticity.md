# ADR-0005: Explicit data modes and demo authenticity

- Status: accepted
- Date: 2026-08-15
- Owners: aistanbulresearch
- Related tasks: RCL-205, RCL-208, RCL-404, RCL-503, RCL-506, RCL-802, RCL-904 through RCL-906
- Supersedes:

## Context

Recall needs a reliable four-minute demonstration without real patient data or misleading claims about synthetic, replayed, cached, mocked, or live information. Previous work showed that hard-coded or mislabeled presentation values can invalidate otherwise strong engineering.

## Decision drivers

- no real patient data;
- reproducible demo timing;
- honest production-data interpretation;
- exact UI-to-artifact lineage;
- no static result labels or hidden fallback data.

## Options considered

1. Fully live demo. Rejected as too dependent on source availability and timing.
2. Fully mocked demo. Rejected because it does not prove production-source or managed-path behavior.
3. Synthetic institutional case plus source-attributed captured replay, with a separately labeled live public smoke test. Accepted.

## Decision

Every artifact and product surface carries exactly one mode: `SYNTHETIC`, `CAPTURED_REPLAY`, `LIVE_PUBLIC`, or `MOCK`. The core demo uses synthetic case identity and a deterministic public-evidence replay. A separate labeled live smoke proves current connector behavior.

All result-bearing UI fields resolve through the derived-value registry to an artifact ID and JSON path.

## Consequences

- The main demo remains stable and honest.
- Replay capture, source hashes, and licensing records are required.
- Live source results cannot silently populate replay screens.
- Jargon-free labels must still preserve mode precision.

## Failure modes

- replay presented as live;
- synthetic data presented as production patient data;
- UI badge remains unchanged when the source artifact changes;
- cached fallback is used without a mode change;
- demo timestamp implies real elapsed weeks.

## Verification and evidence

- mode required by schemas and API responses;
- UI mode badge derived from `DataModeReceipt`;
- artifact mutation test updates every dependent screen value;
- replay manifest with source URLs, timestamps, hashes, and license notes;
- video audit confirms all accelerated and non-live moments are labeled.

## Rollback or supersession

If a live smoke is unreliable, omit the live claim and keep the captured replay. Never relabel replay or mock data to preserve a demo narrative.
