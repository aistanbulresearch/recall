# Engineering Rules

## Delivery gates

1. **Design gate:** define scope, contracts, invariants, failure behavior, test plan, demo state, and cut conditions.
2. **Implementation gate:** use TDD for new behavior; implement the smallest vertical slice.
3. **Review gate:** inspect authority boundaries, scientific logic, security, error handling, and maintainability.
4. **Verification gate:** run positive, negative, failure, and mechanism-activation checks.
5. **Evidence gate:** save reproducible artifacts and connect claims and score rows.
6. **Merge gate:** update status, handoff, work/error/decision logs, and master-plan task state.

## Coding baseline

- Python uses `uv`, type hints, immutable configuration where practical, and strict Pydantic contracts.
- Unknown contract fields are rejected by default.
- Frontend and backend consume generated or shared contract definitions where feasible.
- Deterministic rules are isolated from model prompts and independently tested.
- External source adapters use allowlists, timeouts, bounded retries, rate limits, schema validation, and fixture mode.
- Every event handler is idempotent.
- Every state change has a run ID, artifact ID, source hash, producer version, and reason code.
- Logs and traces exclude raw clinical text and secrets.
- Model outputs are untrusted inputs until schema and policy checks pass.

## TDD expectations

Tests are written before implementation for:

- state transitions and terminal outcomes;
- authority and tool denials;
- privacy detector behavior;
- contract rejection;
- duplicate delivery;
- retry and timeout budgets;
- loop detection;
- citation mismatch and fabrication;
- missing and partial evidence;
- UI value derivation.

Coverage percentage is not a substitute for these behavior gates.

## Fail-loud contract

Every material failure must provide:

- stable error code;
- affected run and step;
- failed input artifact references without sensitive content;
- retry count and terminal reason;
- whether any downstream action occurred;
- trace ID;
- operator-visible state.

No broad `completed` state may conceal a failed mandatory step.

## Review checklist

- Does the code create new authority for a model or agent?
- Can missing data be mistaken for a clean or benign result?
- Can an external document trigger instructions or arbitrary URLs?
- Can the same event produce a duplicate task?
- Can a worker loop exceed its budget?
- Can a failed audit be bypassed?
- Is every UI value traceable to an artifact field?
- Does the failure path have a visible demo and test artifact?
- Are live, replay, synthetic, cached, and mock states labeled?
- Are secrets and sensitive data excluded from Git, logs, traces, and screenshots?
