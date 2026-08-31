---
name: recall-collaboration
description: Coordinate scoped Codex subagents in the Recall repository. Use when work requires delegation, parallel read-only investigation, specialized implementation, independent gate review, agent disagreement resolution, or changes affecting privacy, safety, science, evidence, provenance, eligibility, GitHub publication, or a phase gate.
---

# Recall Collaboration

Keep the primary session as the coordinator and owner-facing control point. Delegate only independent, substantive work and verify every agent claim against repository evidence.

## Start from project truth

1. Read `AGENTS.md`, `docs/project/STATUS.md`, `docs/project/MASTER_PLAN.md`, and `docs/project/HANDOFF.md`.
2. Read the relevant architecture, contract, ADR, evaluation, or runbook.
3. For cross-document questions, use the Recall no-stamp Graphify runner defined in `AGENTS.md`. Never use raw Graphify traversal on this checkout.
4. Inspect the live source, diff, tests, logs, and artifacts. Graph nodes and documentation are design evidence, not runtime proof.
5. State the design, acceptance criteria, file ownership, and stop conditions before implementation.
6. Before a long document, large implementation, architecture change, or scope expansion, present the intended work to the owner and wait for approval.

## Coordinate work

- Use `recall-scout` for focused read-only discovery. Run scouts in parallel only for distinct questions and do not duplicate investigations.
- Use `recall-worker` for bounded implementation with clear acceptance tests.
- Use `recall-smart-worker` only for difficult implementation, integration, or material ambiguity.
- Give every writing agent exclusive ownership of exact files or modules. Never permit overlapping mutable ownership or parallel writes to the same dependency surface.
- Issue an explicit writer lease before each writing assignment and release it only after the agent stops and the coordinator inspects the diff and tests. Do not start a dependent writer while a lease is open.
- Reserve `STATUS.md`, `MASTER_PLAN.md`, `HANDOFF.md`, project logs, evidence ledgers, and dependency lockfiles for the coordinator or one explicitly designated finalizer.
- Tell every leaf agent that it is not alone in the repository, must preserve others' changes, must finish the assignment directly, and must not spawn agents.
- Keep at most three spawned threads active so the coordinator remains available within the four-thread budget.
- Prefer one writer and one independent reviewer over multiple writers when boundaries are coupled.

Every assignment must state: objective, owned paths, read-only dependencies, out-of-scope work, acceptance criteria, required tests, evidence to return, stop conditions, and the no-spawn rule.

## Preserve owner authority

Only the owner may approve scope expansion, destructive actions, GitHub writes, commits, pushes, merges, releases, cloud changes, billing decisions, or external publication. Agents may prepare evidence and recommendations but must stop before those actions unless the owner explicitly authorizes the exact operation.

The coordinator, not a subagent, communicates approval requests and final status to the owner. A reviewer verdict never replaces owner approval.

## Verify before synthesis

- Do not treat another agent's summary as evidence.
- Read the changed files and diff directly.
- Re-run relevant tests or inspect the exact immutable artifacts and raw logs.
- Distinguish specification, implementation, executed verification, accepted external write, and independent mechanism-level proof.
- Treat missing evidence as `NOT VERIFIED`; never infer clean or safe from an empty result.
- Require guardrail activation plus proof that the forbidden downstream effect did not occur.

## Run independent gates

Invoke `recall-master-judge`:

- after design and acceptance criteria are complete;
- after implementation and tests;
- after every two completed writing-agent assignments in a long task;
- immediately on agent disagreement;
- for any privacy, safety, scientific-validity, evidence, provenance, or eligibility change;
- before every commit, push, merge, release, or phase gate.

Run the judge only against a stable worktree after all in-scope writer leases are released.

The judge is read-only and must not repair its own findings. Apply the verdict contract in [master-judge-rubric.md](references/master-judge-rubric.md).

After a stable remote checkpoint is owner-published, request the separate external GitHub auditor after every two completed writing-agent assignments or three remote commits, whichever occurs first. Request it sooner for a high-risk change and always before merge or phase exit. This external auditor is outside the Codex hierarchy and does not replace the Master Judge.

## Close the work unit

1. Resolve all required findings or report the gate as failed.
2. Re-run the exact acceptance checks after fixes.
3. Update Recall's required status, work, error, decision, handoff, and evidence records.
4. Report exact changed paths, executed checks, evidence boundaries, current gate, and next task.
