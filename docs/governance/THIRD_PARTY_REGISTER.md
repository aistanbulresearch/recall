# Third-Party Component and Data Register

- Status: initial planning inventory
- Task: RCL-102
- Updated: 2026-08-16

`approved candidate` means the named component's current license or terms have been reviewed for the planned role. It does not authorize an unpinned version or an unreviewed transitive graph.

| Component or source | Planned role | Terms class | Distribution mode | Current decision | Required condition |
|---|---|---|---|---|---|
| Recall source and documentation | Project work product | Apache-2.0 | Git repository and distributions | Approved | Preserve the repository `LICENSE`; third-party components remain governed separately. |
| Google Agent Development Kit for Python | Multi-agent framework | Apache-2.0 | Python dependency and container | Approved candidate | Pin exact version and transitive graph; preserve notices. |
| Google Cloud Python client libraries | Firestore, Pub/Sub, Secret Manager, Vertex and platform access | Package-specific open-source licenses plus Google Cloud service terms | Python dependencies and remote services | Conditional | Verify every exact package and transitive license in the lock; accept and recheck service terms. |
| Pydantic | Strict typed contracts | MIT | Python dependency | Approved candidate | Pin exact version and transitive graph; preserve notice. |
| FastAPI | API edge candidate | MIT | Python dependency and container | Approved candidate, not architecture-selected | Confirm under implementation design; pin exact version and transitive graph. |
| `llama.cpp` | Local Gemma inference runtime candidate | MIT | Local binary or locally built runtime | Approved candidate | Pin source/release and hash; review build dependencies; isolate runtime. Runtime license does not cover weights. |
| Gemma model artifacts | Residual identifier span proposals | Custom Gemma Terms and Prohibited Use Policy | Separately downloaded or mounted local artifact | Conditional | No Git/release/container redistribution; operator accepts terms; pin source and hash; synthetic-only contest data; no clinical or workflow decision. |
| Gemini on Google Cloud | Agent reasoning in contest path | Google Cloud agreement and Service Specific Terms | Remote managed service | Conditional, non-clinical only | Synthetic non-clinical research prototype; no clinical-production claim; terms recheck at freeze and submission. |
| Gemini Enterprise Agent Platform components | Runtime, Registry, governed extensions, and observability | Google Cloud agreement, service terms, and product-specific documentation | Remote managed services | Conditional | Billing/access smoke, region and Pre-GA status, exact service terms, outage contract, and no regulated data in unsupported Pre-GA services. |
| ClinVar | Public variant evidence and historical replay | NCBI/ClinVar data policy | Live retrieval and attributed captured replay | Conditional | Provenance, weekly-release/retrieval date, attribution, professional-review disclaimer, and no direct diagnostic-use claim. |
| NCBI E-utilities and PubMed metadata | Literature discovery and citation metadata | NCBI usage policy plus third-party abstract copyright | Live retrieval and limited captured metadata | Conditional | `tool`/`email`, rate limits, visible disclaimer, and no redistribution of full abstracts or full text without rights. |
| NCBI GEO `GSE248438` | Exact public BRCA2 functional-data row for RCL-205 captured replay | NCBI GEO public data service and record-level provenance | Hash-pinned retrieval plus minimum derived row; no article redistribution | Approved for RCL-205 selection; implementation conditional | Preserve accession, official locator, exact binary hash, source columns, and non-clinical disclaimer; fail on retrieval/hash mismatch. |
| Web framework and UI packages | Reviewer application | Not selected | Web build and container | Blocked pending selection | RCL-207 must select the stack; exact lock, license review, SBOM, and notices are required before use. |
| Fonts, icons, screenshots, and demo media | Public demo presentation | Asset-specific | Public website and video | Blocked until inventoried | Record source, license, attribution, modification rights, and distribution rights for every asset. |
| Container base images | Reproducible deployment | Image-specific licenses | Distributed deployment images | Blocked until selected | Immutable digest, SBOM, vulnerability scan, and notice review. |

## Not approved by this register

- Any dependency named only in a design document but absent from an exact lock.
- Any transitive package not present in the generated SBOM.
- Any Hugging Face or other model mirror whose publisher, terms, and artifact hash are not verified.
- Any full-text article, abstract corpus, proprietary database, benchmark dataset, image, font, or icon not listed above with exact rights.
- Any package or asset copied from another project.

## Required implementation update

RCL-301 replaces planning rows with exact package versions, integrity hashes, direct/transitive classification, license identifiers, and review results. Each build manifest references the resulting SBOM hash.
