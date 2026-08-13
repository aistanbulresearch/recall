# Decision Log

Append-only. Supersede decisions with a new entry rather than deleting history.

## DEC-2026-08-14-001: Product name

- Status: accepted
- Decision: Name the project **Recall** and use the repository `aistanbulresearch/recall`.
- Consequence: Run a naming-collision and discoverability review before public launch; do not change the owner-selected name without a new decision.

## DEC-2026-08-14-002: Demo is part of the product

- Status: accepted
- Decision: Build the web experience with every vertical slice instead of after backend completion.
- Reason: Demo represents 30% of judging and previous experience showed that invisible depth earns no score.
- Consequence: A backend task is incomplete until its authoritative state and failure behavior are visible where relevant.

## DEC-2026-08-14-003: Structural safety authority

- Status: accepted
- Decision: LLM components may propose and audit typed artifacts but cannot own state transitions, classification, notification, or terminal outcomes.
- Consequence: Workflow Controller, Ledger API, and Policy Gate remain deterministic enforcement components.

## DEC-2026-08-14-004: Derived presentation values

- Status: accepted
- Decision: Every displayed result must be computed from the exact authoritative artifact for that run.
- Consequence: No hard-coded outcome, threshold label, status badge, metric, or chart value is permitted.

## DEC-2026-08-14-005: Repository authorship

- Status: accepted
- Decision: All Git and GitHub authorship must resolve to `aistanbulresearch`; no co-author, generated-by, assistant, or automation attribution trailers are allowed.
- Consequence: Identity verification is a pre-commit and pre-push gate.

## DEC-2026-08-14-006: Git branch simplification

- Status: accepted
- Decision: Use `main` plus short-lived feature branches rather than adding a long-lived `develop` branch initially.
- Reason: Preserve review gates while avoiding unnecessary hackathon integration overhead.

## DEC-2026-08-14-007: Deployment hostname unresolved

- Status: pending owner clarification
- Context: The product is Recall, while the supplied hostname was `racall.aistanbulresearch.com`.
- Decision: Do not mutate DNS or deployment configuration until the owner confirms the spelling.
