# GitHub Auditor Re-review

- Date: 2026-08-17
- Remote PR: `#2`
- Reviewed head: `05ff0b59cad88ef00adc2be2e239e57f73226cda`
- Remote authorship: owner-only `aistanbulresearch`
- First re-review verdict: `FAIL`
- Remediation state: owner-only remote remediation published; final remote metadata correction in progress

## Remote publication evidence

The correction package was committed as `fix(architecture): close phase 2 audit` and pushed by `aistanbulresearch`. GitHub read-back matched the local SHA and showed `aistanbulresearch` as commit author, committer, and PR owner. No co-author trailer or non-owner commit identity was present.

Cursor then created another `cursor[bot]` upsell comment. The exact comment was deleted. Two bounded rereads found zero issue comments, review comments, reviews, and checks. The recurrence proves that Cursor GitHub integration disablement was not established, so no further push is authorized yet.

A later `user/installations` probe returned HTTP 403 because the token is not authorized as a GitHub App, so installed-app state remains unknown. Independent fail-loud endpoint checks still report zero issue comments, zero review comments, and zero reviews. A clean visible surface is not treated as proof that Cursor is disabled.

## Auditor findings

| Finding | Severity | Remote evidence | Local remediation |
|---|---|---|---|
| Ambry citation narrative included both 2025 studies | High | Frozen ClinVar v5 cites PMID 39779848 only | Case narrative now says Ambry cites Sahu only; Huang is separate corroborating literature |
| Verifier counters and chronology were overstated | High | Counters were constants and later dates came from manifest arithmetic | Counters now derive from successful assertions; PubMed/ClinVar source dates and classifications are parsed; semantic mutation tests rebind hashes and still fail |
| Capture root could escape before final rejection | High | Invalid root recorded a failure but processing continued | Invalid root now throws before capture access; lexical, absolute, parent, and target-bearing junction paths have fault tests |
| Rights metadata did not meet policy | Medium | Rights were aggregate and raw/normalized roles were implicit | Manifest now binds every source to reviewed official terms, explicit permissions, raw/normalized hash roles, limitations, attribution, and redistribution boundaries |

## Local verification after remediation

```text
status=PASS
verified_captures=10
verified_bytes=1400869
chronology_checks=7
source_semantic_checks=12
rights_metadata_checks=11
live_connector_spec_checks=1
exact_xlsx_rows=1
network_calls=0
```

The expanded fault harness rejects changed bytes, lexical traversal, absolute and parent roots, hash-rebound ClinVar citation drift, hash-rebound Nature excerpt word-count drift, invalid captured and live rights-profile bindings, invalid hash-role bindings, and a junction escape. This is local evidence only and is not remote evidence.

## Second local review

The second read-only review returned `FAIL` with two Medium findings. It confirmed that all first-review High findings were closed, but found that the unexecuted live connector lacked a rights binding and that the displayed 22-check counter mixed rights review dates with source semantics without an exact harness assertion.

The local remediation now declares the live source as `UNEXECUTED_CONNECTOR_SPEC` with explicit null byte roles, NCBI rights profile, limitations, attribution, and runtime hash/timestamp rule. The verifier reports separate exact-ID sets: 12 source semantic checks and 11 rights metadata checks. The harness asserts both complete sets and mutates the live rights profile.

## Third local review

The third read-only review returned `FAIL` with one Medium finding. It confirmed prior findings closed but demonstrated that the live runtime provenance rule, locator, and semantic anchor were not verifier-enforced.

The local remediation now validates the allowlisted HTTPS locator, semantic anchor, non-empty integrity rule, and a structured runtime provenance contract. That contract requires `data_mode`, `raw_sha256`, `retrieved_at`, `semantic_anchor`, and `source_locator`, fixes SHA-256 and `LIVE_PUBLIC`, and forbids captured-replay hash comparison. A distinct `live_spec:clinvar_positive_current_xml` success ID is harness-asserted, and an empty runtime rule is fault-injected.

## Fourth local review

The fourth read-only review returned `FAIL` with one Medium finding. It reproduced a duplicate live-source false pass because only captured IDs were registered in the global uniqueness set and the success-ID set collapsed duplicates.

The local remediation now registers live source IDs in the same global set as captured sources, rejects cross-class or within-live duplicates as `source_id_duplicate`, asserts `live_public_sources=1`, and fault-injects a duplicated live spec.

## Fifth local review

Verdict: `PASS`. No actionable findings remain. The auditor independently confirmed global captured/live source-ID uniqueness, exact clean-result live count and check sets, duplicate-live and cross-class collision rejection, runtime provenance enforcement, citation scope, path/junction controls, PowerShell 5.1 behavior, and absence of prohibited authorship signatures.

## First final remote review

Verdict: `FAIL` on two Medium remote-metadata findings only. Exact remote head `fb469ea920f96a03002f298e4947aeba4fd5dd0a` passed the committed PowerShell 5.1 verifier and full harness; all seven PR commits resolved author, committer, and GitHub actor only to `aistanbulresearch`; comments, review comments, reviews, statuses, and check runs were zero. The remaining findings were stale counts in the PR body and a STATUS row that incorrectly called remediation checkpoint `9cfee558` the current head.

The PR body was corrected through the authenticated owner web interface after repeated API writes returned HTTP 503, then read back through the GitHub API. STATUS now describes `9cfee558` as the remediation checkpoint and avoids a self-stale exact SHA for its documentation successor. These corrections require a final exact-head remote review.

## Gate

The code/source-package audit passes, but merge and Phase 3 remain `NO-GO` until this final metadata correction is published owner-only, delayed actor surfaces remain clean, and the exact remote head passes the final re-review.
