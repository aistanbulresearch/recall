# Contributing

Read `AGENTS.md`, `docs/project/STATUS.md`, `docs/project/MASTER_PLAN.md`, and `docs/project/HANDOFF.md` before making changes.

## Workflow

1. Select a master-plan task ID.
2. Define or confirm acceptance criteria.
3. Create `feature/<task-id>-<slug>`.
4. Write tests before new behavior.
5. Implement the smallest vertical slice, including its visible web state where relevant.
6. Run positive, negative, fault, and guardrail-activation checks.
7. Update status, handoff, work/error/decision logs, and evidence ledgers.
8. Open a pull request with evidence and rollback information.

Use Conventional Commits. Repository authorship must comply with `docs/governance/GIT_ATTRIBUTION_POLICY.md`.

## Pull-request minimum

- linked task and decision IDs;
- problem and scope;
- changed authority or trust boundary, if any;
- tests and exact verification commands;
- evidence artifact paths;
- screenshots for visible changes;
- risks and rollback;
- documentation updates;
- confirmation that no secret, real patient data, or unsupported claim was added.
