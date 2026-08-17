# Recall Working Agreement

These instructions apply to every contributor and automation operating in this repository.

## Communication and approval

- Work with the project owner in Turkish unless a deliverable is explicitly English.
- Repository documentation, code, identifiers, comments, submission text, and demo script are English unless otherwise requested.
- Keep status messages concise and evidence-based.
- Before starting a long document, large implementation, architecture change, or scope expansion, summarize the intended work and ask whether the owner wants to add anything.
- Do not guess when a missing answer can materially change product behavior, scientific validity, eligibility, privacy, or deployment.
- Offer an independent technical view. Do not optimize for agreement.

## Mandatory delivery sequence

Every non-trivial change follows:

1. design and acceptance criteria;
2. implementation with tests;
3. independent review or explicit self-review record;
4. verification against real artifacts;
5. documentation and evidence-ledger update;
6. merge only after the gate passes.

Stop and report at each gate. Do not hide a failed gate by continuing into later work.

## Scientific and safety rules

- Scientific consistency is not negotiable.
- Never hard-code a displayed result or manipulate a fact for the demo.
- Every displayed number must be derived from the exact run artifact behind the screen.
- Missing data is unknown, not clean, negative, benign, or safe.
- Fail loudly with a typed failure record.
- An LLM may propose, summarize, or challenge. It may never classify, notify, or create a terminal clinical outcome.
- Model restrictions must be enforced by architecture, identity, tool scope, schema, and deterministic policy, not only by prompt text.
- A guardrail claim is valid only after a test visibly triggers that guardrail.
- Synthetic, recorded, replayed, cached, mocked, and live data must be labeled accurately at every surface.
- Never use real patient data in development, repository history, screenshots, logs, traces, or the public demo.

## Demo-first product rule

- The web application is a first-class product surface, not a post-development presentation layer.
- Every vertical slice must update the backend behavior, audit artifact, and visible demo state together.
- Build the contrast into the interface: show the standard autonomous-agent failure, then show why Recall makes that failure structurally impossible.
- Prefer one clear, visible, end-to-end action over several invisible capabilities.
- The demo must be understandable without genetics expertise.

## Independent implementation boundary

- Recall is a new project implemented independently in this repository.
- Do not copy source code, tests, fixtures, schemas, prompts, configuration, UI, documentation, generated artifacts, or commit history from another project.
- Other codebases may be inspected only to understand abstract engineering patterns, failure modes, or lessons. Re-derive the Recall design and implementation from its own requirements and acceptance tests.
- Do not create a voluntary public `pre-existing work` section when no component is imported or reused.
- If a binding rule or submission field explicitly asks about prior work, inspiration, or reuse, stop and review its exact wording before answering truthfully and narrowly.

## Documentation protocol

Before work, read:

1. `docs/project/STATUS.md`
2. `docs/project/MASTER_PLAN.md`
3. `docs/project/HANDOFF.md`
4. the relevant architecture, ADR, evaluation, or runbook

After substantive work, update:

- `STATUS.md` with the current true state;
- `WORK_LOG.md` with actions and verification;
- `ERROR_LOG.md` for every material error or failed attempt;
- `DECISION_LOG.md` when a decision changes;
- the score, claim, guardrail, and demo ledgers when evidence changes;
- `MASTER_PLAN.md` whenever scope, sequencing, dates, status, or gates change;
- `HANDOFF.md` so another contributor can continue without oral context.

Do not claim completion based on an accepted write, a green UI, or a zero-finding report alone. Record the independent mechanism-level proof.

## Git and authorship

- The repository owner is `aistanbulresearch`.
- Before every commit and push, verify the local Git author/committer and active GitHub account.
- Do not add `Co-authored-by`, generated-by, assistant attribution, or automated authorship trailers.
- Commit and PR authorship must resolve to `aistanbulresearch`.
- Do not request or retain automated assistant/bot review comments, review records, authorship badges, or generated-by notices on GitHub. Inspect PR comments and reviews after creation and every push; remove unsolicited assistant/bot attribution when repository permissions allow it, and report any recurrence.
- Use Conventional Commits and small, single-purpose commits.
- Never commit secrets, local model weights, real clinical data, token maps, private keys, raw traces, or unreviewed generated artifacts.
- Do not rewrite published history or force-push without explicit owner approval.

## Current product invariants

- The hackathon deployment is a non-clinical research prototype using synthetic institutional records and approved public evidence.
- Anonymization or pseudonymization does not by itself authorize a prohibited clinical use. Future clinical deployment requires a separate provider-terms, regulatory, privacy, security, and validation gate.
- Lab-local privacy approval precedes any cloud-bound payload.
- The deterministic Workflow Controller owns state, budgets, retries, loop detection, and agent invocation.
- Agents use narrow tools and append-only typed artifacts. They do not write authoritative state directly.
- The independent Citation Auditor cannot be skipped for a trusted review recommendation.
- Only the deterministic Policy Gate may emit `NO_ACTION`, `ABSTAIN`, or `REVIEW_REQUIRED`.
- If trusted policy execution or ledger integrity is unavailable, the Controller records technical `HALTED`; it must not fabricate a Policy Gate outcome.
- Firestore is authoritative; model memory is not clinical evidence.
- Clinicians retain final decision authority.

## Recall Graphify agent policy

Recall's document-aware knowledge graph is at `graphify-out/graph.json`. It is
built from the protected live checkout with Gemini `gemini-3.5-flash-lite`
using the versioned `recall-concepts-v1` profile.

For questions about Recall's architecture, policies, contracts, lifecycle, or
cross-document relationships, consult the graph before broad source searches.
On this Windows/OneDrive checkout, do not call raw `graphify query/path/explain`:
Graphify's optional query-stamp write can spin on the OneDrive reparse point.
Use the read-only no-stamp runner instead:

```powershell
$GraphifyPython = 'C:\Users\oacav\graphify-all-repos\gfvenv\Scripts\python.exe'
$GraphifyAgentRunner = 'C:\Users\oacav\graphify-all-repos\graphify_agent_runner.py'
$RecallGraph = '.\graphify-out\graph.json'

& $GraphifyPython $GraphifyAgentRunner query '<question>' --graph $RecallGraph
& $GraphifyPython $GraphifyAgentRunner explain '<concept>' --graph $RecallGraph
& $GraphifyPython $GraphifyAgentRunner path '<A>' '<B>' --graph $RecallGraph
```

If the graph may be stale or the current task needs newly edited documents,
refresh synchronously and wait for exit code 0:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File 'C:\Users\oacav\graphify-all-repos\refresh-repo.ps1' recall
```

A successful refresh must print `Recall graph quality gate: PASS`. The gate
requires concept coverage, a connected `Policy Gate`, complete manifest source
coverage, and no broken edge endpoints. If refresh or the gate fails, use the
last graph only as stale context and disclose that limitation.

The refresh includes uncommitted files but never pulls, resets, commits, or
pushes the live Recall checkout. Semantic extraction is performed by Gemini,
not Claude or Codex. Never print, copy, or persist the Gemini API key.

Graph nodes derived from documentation describe specifications and design
intent. They are not evidence that a feature is implemented or runtime-verified;
inspect executable source and tests before making implementation claims.
