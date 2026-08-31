# ADR-0004: Separate local Gemma privacy detection from Model Armor content security

- Status: accepted
- Date: 2026-08-15
- Owners: aistanbulresearch
- Related tasks: RCL-107, RCL-401 through RCL-406, RCL-610, RCL-707
- Supersedes:

## Context

Recall needs both a lab-local privacy boundary and protection from hostile external content. Treating one generative security product as a universal guardrail would create an unsafe dependency and obscure where raw identity is permitted to exist.

## Decision drivers

- raw patient identity never reaches cloud services;
- Gemma use must add measured value rather than bonus-only decoration;
- deterministic redaction remains authoritative;
- external publication and tool content is untrusted;
- service and language limitations fail loudly.

## Options considered

1. Send raw text to cloud Model Armor for anonymization. Rejected because it violates the lab boundary.
2. Let local Gemma directly redact and approve payloads. Rejected because model output would become authoritative.
3. Use Gemma as a local residual-span proposer and Model Armor as cloud-side untrusted-content screening, with deterministic gates around both. Accepted.

## Decision

Local deterministic detectors run first. Local Gemma proposes residual identifier spans only. Deterministic schema validation, redaction, and outbound scanning decide whether a signed pseudonymous payload may leave the lab.

Model Armor, when available, screens untrusted external source and tool-response content for injection or malicious material. It is not a PHI anonymizer, evidence authority, or policy engine.

## Consequences

- The two models have distinct, explainable jobs.
- Local Gemma requires a measured synthetic corpus and unavailable/invalid-output tests.
- Model Armor becomes optional to scientific correctness but valuable to Fleet governance proof.
- Hostile external content needs a restricted fallback when Model Armor is unavailable.

## Failure modes

- Gemma misses an identifier or returns invalid spans;
- deterministic outbound scan is bypassed;
- Model Armor service outage is treated as clean content;
- unsupported-language performance is overstated;
- blocked content is logged with sensitive raw text.

## Verification and evidence

- seeded identifier corpus and paired deterministic/Gemma metrics;
- invalid JSON, timeout, and unavailable Gemma quarantine tests;
- prompt-injection benign/attack controls for external content;
- service-unavailable behavior and sanitized receipts;
- proof that no raw clinical text reaches cloud telemetry.

## Rollback or supersession

If Gemma fails the preregistered feasibility gate, free text remains local or is rejected; deterministic structured minimization continues. If Model Armor is unavailable, restrict accepted source content to deterministic structured fields or `ABSTAIN`.
