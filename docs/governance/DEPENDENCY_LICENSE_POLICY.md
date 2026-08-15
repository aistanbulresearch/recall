# Dependency, License, API, and Data-Rights Policy

- Status: verified
- Task: RCL-102
- Updated: 2026-08-15
- Scope: source dependencies, transitive packages, model artifacts, hosted APIs, public datasets, containers, demo assets, and generated evidence

This document is an engineering compliance gate, not legal advice. A dependency, model, API, dataset, or asset is prohibited until its exact version or terms are recorded and approved under this policy.

## Decisions

1. Recall will not vendor or copy source from another project.
2. Exact direct and transitive versions must be locked before product implementation.
3. Every distributable artifact must have a reproducible Software Bill of Materials and required notices.
4. Model weights are separate governed artifacts. They are never treated as ordinary source dependencies.
5. Public accessibility does not establish redistribution rights.
6. Unknown, missing, or conflicting license metadata is a blocking result, not an implicit approval.
7. The repository license is Apache License 2.0, approved by the owner after review of the binding Rules snapshot.

## License decision classes

| Class | Default decision | Examples | Required action |
|---|---|---|---|
| Permissive | Allowed after exact-version verification | Apache-2.0, MIT, BSD-2-Clause, BSD-3-Clause, ISC | Preserve copyright/license notices and include the component in the SBOM and third-party notices. |
| Attribution or file-level copyleft | Conditional | CC-BY for suitable non-code assets, MPL-2.0 | Review the exact use and distribution boundary; preserve attribution and notices; document affected files. |
| Weak copyleft | Conditional and normally avoided | LGPL | Require owner review of linking and distribution method before adoption. |
| Strong or network copyleft | Blocked for contest scope unless explicitly approved | GPL, AGPL | Do not add without a recorded owner and legal review of distribution obligations. |
| Source-available or field-of-use restricted | Blocked by default | SSPL, BSL/BUSL, Commons Clause, non-commercial, research-only | Do not add without a specific written exception and compatibility review. |
| Custom model or data terms | Conditional | Gemma Terms, API-specific terms, dataset terms | Record exact version/date, access method, redistribution boundary, prohibited uses, and notice requirements. |
| Unknown or no license | Blocked | Unlicensed repository, ambiguous asset, undocumented model mirror | Stop. Obtain authoritative terms or select another component. |

An OSI label alone is not sufficient. The exact license text, resolved version, transitive graph, and how Recall distributes or hosts the component determine the final decision.

## Dependency admission gate

Before a package enters a lock file or container, record:

- canonical package and source repository;
- exact resolved version and integrity hash;
- direct or transitive status;
- purpose and importing component;
- license identifier and authoritative license URL;
- whether the package is copied, linked, containerized, or used only as a remote service;
- required notices, source-offer, attribution, or redistribution conditions;
- known security advisory result;
- decision owner, date, and `approved`, `conditional`, or `blocked` status.

The gate fails if any resolved component has unknown license metadata, an unreviewed custom license, a blocked license, a known unmitigated critical vulnerability, or a source URL that does not match the expected publisher.

## Locking and software inventory

- Python uses `uv` with an exact lock. Unbounded production dependencies are prohibited.
- The web package manager and framework will be selected under RCL-207. No JavaScript dependency is pre-approved by this document.
- Container base images must use immutable digests and have their own license and vulnerability records.
- Development-only dependencies are inventoried even when they are not shipped.
- Dependency upgrades reopen the license and security gate for the changed transitive graph.
- RCL-301 must produce a CycloneDX or SPDX SBOM from the exact clean-clone build.
- RCL-902 must regenerate and compare the SBOM at feature freeze.

## Required repository artifacts

Before the first distributable build, create and maintain:

- `LICENSE`;
- `THIRD_PARTY_NOTICES.md` generated from the reviewed lock and corrected manually where required;
- a machine-readable SBOM under the evidence artifact for the build;
- `docs/governance/THIRD_PARTY_REGISTER.md`;
- a model terms and artifact record for every downloaded model;
- a data-source register for every replay or live connector.

Generated notices are not accepted solely because the generator exited successfully. The input package count, output component count, unknown-license count, and blocked-license count must be checked independently.

## Model and runtime rules

- Model weights, tokenizers, quantizations, adapters, and runtime binaries require separate provenance, terms, hash, and source records.
- Gemma is governed by custom terms and a prohibited-use policy. It is conditional, not open-source-permissive.
- Gemma weights must not be committed, attached to GitHub releases, or baked into a public Recall image.
- The contest setup must download or mount Gemma separately only after the operator accepts the applicable terms.
- `llama.cpp` is a candidate MIT-licensed runtime, but its license does not grant rights to any model weights loaded into it.
- Only allowlisted model repositories and pinned artifact hashes may be used.
- Untrusted model artifacts execute only in a constrained local environment with no repository, credential, token-vault, or network access beyond the explicit need.
- Gemma may propose identifier spans. It cannot approve egress or make a clinical or workflow decision.

## Hosted service terms

- Google Cloud and Gemini use is governed by the current account agreement and service-specific terms, not by the open-source licenses of client libraries.
- The competition build is a non-clinical research prototype using synthetic institutional records and approved public evidence.
- Any contest `ReviewTask` is a visibly simulated artifact for a synthetic case and is not routed to a real clinical workflow.
- The current Google Cloud Service Specific Terms prohibit Generative AI Services for clinical purposes. Therefore no Recall claim, deployment, test, or demo may represent the Gemini path as authorized for clinical production.
- De-identification does not change a prohibited purpose into an allowed purpose.
- A future laboratory production deployment requires a separate terms, regulatory, privacy, and contract review before real data or clinical use.
- Pre-GA services must not process personal or regulated data unless their specific written terms expressly permit it.
- Service terms and relevant prohibited-use policies must be rechecked at feature freeze and before submission.

## Public evidence and data rights

### ClinVar

- Record accession, source URL, release or retrieval date, and content hash for every captured replay.
- Attribute ClinVar in the product and publications when its data is copied or distributed.
- Preserve the warning that submissions are not independently verified and are not for direct diagnostic or medical decision-making without genetics-professional review.
- Treat missing or failed ClinVar retrieval as unknown and fail loudly.

### PubMed and NCBI E-utilities

- Send requests only to the documented E-utilities endpoint.
- Configure `tool` and `email` through deployment configuration; do not publish a private contact address in source.
- Limit requests to no more than three per second without an NCBI API key and follow NCBI scheduling guidance for large jobs.
- Make the NCBI disclaimer and copyright notice evident to users.
- PubMed abstracts can remain copyrighted by publishers or authors. Recall may store identifiers, bibliographic metadata, licensed text, short evidence excerpts where lawful, and derived structured claims. It must not redistribute full abstracts or full text without verified rights.

### Replay and live-data manifests

Every captured or live data artifact records:

- `data_mode`;
- canonical source and accession or stable identifier;
- retrieval timestamp and source release where available;
- raw-content hash and normalized-artifact hash;
- license or terms URL and review date;
- permitted retention and redistribution;
- transformation steps;
- known limitations and attribution text.

No connector may follow arbitrary model-proposed URLs. Source domains and endpoint patterns are deterministic allowlists.

## CI and release gates

The implementation phase must add checks that fail on:

- lock-file drift;
- unpinned container bases;
- unknown or blocked licenses;
- a package present in the lock but absent from the generated inventory;
- a model artifact present in Git history or a release asset;
- missing required notices or attribution;
- a captured replay without rights/provenance fields;
- terms whose required recheck date has expired;
- clinical-production wording for the contest Gemini deployment.

Exceptions require an append-only decision record with exact scope, rationale, owner, expiry, and rollback. No exception may override contest rules, provider terms, or the no-real-patient-data rule.

## RCL-102 completion condition

The policy, source notes, initial register, and owner-approved Apache-2.0 repository license are complete. RCL-102 is `verified`. Exact versions and transitive approvals remain implementation gates under RCL-301, not a reason to preselect packages now.
