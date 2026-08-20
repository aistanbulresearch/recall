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

The owner authorizes the registered `Graphify-Refresh-All` automation to run
`refresh-repo.ps1 -All -NoBackup` every two hours against the protected Recall
checkout. This standing authorization is limited to the existing supported
corpus, Gemini destination, `gemini` backend, `gemini-3.5-flash-lite` model,
`recall-concepts-v1` profile, 5000-token extraction budget, task principal,
logging destination, and privilege. The automation may fingerprint the local
corpus and profile. When both fingerprints are unchanged, it must skip Gemini
extraction. When either fingerprint changes, it may transmit only the configured
supported Recall corpus to Gemini semantic extraction and missing-label
generation within that fixed scope. Logs must not contain credentials or private
source contents.

Any change to cadence, source roots, supported file classes, destination,
backend, model, profile, token budget, logging destination, task principal, or
privilege requires a new explicit owner authorization. Manual or ad-hoc refresh
does not inherit the recurring automation authorization: before each manual run,
obtain explicit owner authorization for its private payload class and Gemini
destination. Without that manual authorization, use the existing graph as stale
context and disclose the limitation.

After explicit manual authorization, if the graph may be stale or the current
task needs newly edited documents, refresh synchronously and wait for exit code
0:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File 'C:\Users\oacav\graphify-all-repos\refresh-repo.ps1' recall
```

A successful refresh must print `Recall graph quality gate: PASS`. The gate
requires concept coverage, a connected `Policy Gate`, complete manifest source
coverage, and no broken edge endpoints. If refresh or the gate fails, use the
last graph only as stale context and disclose that limitation.

The Recall refresh currently runs its required `label`/cluster-only step after
the printed quality gate, and that step can rewrite the root graph totals.
After the process exits, directly reconcile the final root `graph.json` and
`GRAPH_REPORT.md` counts, manifest coverage, and broken endpoints. Report the
post-label root artifact as a timestamped snapshot with graph/report hashes and
the reported build commit; retain any pre-label gate totals only as stage-specific
evidence. Never describe hard-coded Graphify counts as unscoped current truth.
Future handoffs must either cite a dated, hash-bound snapshot or instruct the
incoming agent to run the read-only quality gate and final-root reconciliation.

For changed recurring runs, extraction, Recall quality-gate, labeling, or global
add failure stops the changed-run path before freshness fingerprints are updated.
This is source-level behavior of the inspected runner, not proof that scheduler
identity, permissions, execution, or failure handling worked at runtime.

The refresh includes uncommitted files but never pulls, resets, commits, or
pushes the live Recall checkout. Semantic extraction is performed by Gemini,
not Claude or Codex. Never print, copy, or persist the Gemini API key.

Graph nodes derived from documentation describe specifications and design
intent. They are not evidence that a feature is implemented or runtime-verified;
inspect executable source and tests before making implementation claims.
