# Recall Status

## Snapshot

| Field | Current truth |
|---|---|
| Updated | 2026-08-14 |
| Phase | Phase 0 verified; Phase 1 awaiting owner review |
| Overall state | Foundation complete, product work not started |
| Product code | Not started |
| Deployment | Not started |
| Scientific validation | Not performed |
| Clinical validation | Not performed |
| Demo surface | Not started |
| GitHub | Private repository with verified documentation baseline on `main` |
| Local checkout | Created at `C:\Users\oacav\OneDrive\Desktop\recall project` |

## Completed

- Product name changed to **Recall**.
- GitHub repository `aistanbulresearch/recall` verified as private and initially empty.
- Local checkout created at the owner-specified path.
- Contest target architecture and guardrail direction were previously designed and are being normalized into Recall documentation.
- Owner supplied mandatory lessons, engineering principles, authorship constraints, hosting target, and documentation requirements.
- Initial living plan, documentation protocol, operating principles, and evidence-ledger structure drafted.
- Documentation baseline pushed and read back at `5336432a3e353261813443f41a217388b68d585d`; GitHub author and committer are `aistanbulresearch`.
- Recall Obsidian project memory bootstrapped and synthesized; local absolute paths remain Git-ignored.

## In progress

- Owner review of the Phase 0 plan and open decisions.

## Blocked

- Final hostname configuration: `recall` versus the written `racall` spelling requires owner confirmation.
- No external deployment work should begin before access and security gates.

## Not started

- Platform smoke tests.
- Local Gemma benchmark.
- Product implementation and TDD.
- Privacy/evidence/reliability evaluation.
- Reviewer web application.
- Hetzner deployment and DNS.
- Demo recording and submission.

## Current risks

| Risk | Severity | Response |
|---|---|---|
| Domain-specific value may be unclear to the jury | High | Lead with specialist workload and show one visible action; minimize jargon. |
| Deep architecture may remain invisible | High | Map every control to a web state, trace, denial, or failure receipt. |
| Green tests may not exercise guardrails | High | Require activation counters and fault-injection evidence. |
| UI values may drift from backend artifacts | Critical | Maintain derived-value lineage and prohibit hand-entered result values. |
| Schedule may leave insufficient demo time | Critical | Build the web surface with each slice and freeze features on August 28. |
| Product name may have discoverability/confusion risk | Medium | Run naming-collision review before public launch. |

## Next three actions

1. Confirm hostname spelling and review the master schedule with the owner.
2. Run Phase 1 eligibility, platform-access, secret, license, and Gemma feasibility gates.
3. Freeze architecture contracts, evaluation protocols, and demo storyboard before code implementation.
