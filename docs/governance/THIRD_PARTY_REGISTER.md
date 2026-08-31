# Third-Party Component and Data Register

- Status: initial planning inventory
- Task: RCL-102
- Updated: 2026-08-22

`approved candidate` means the named component's current license or terms have been reviewed for the planned role. It does not authorize an unpinned version or an unreviewed transitive graph.

| Component or source | Planned role | Terms class | Distribution mode | Current decision | Required condition |
|---|---|---|---|---|---|
| Recall source and documentation | Project work product | Apache-2.0 | Git repository and distributions | Approved | Preserve the repository `LICENSE`; third-party components remain governed separately. |
| Google Agent Development Kit for Python | Multi-agent framework | Apache-2.0 | Python dependency and container | Approved candidate | Pin exact version and transitive graph; preserve notices. |
| Google Cloud Python client libraries | Firestore, Pub/Sub, Secret Manager, Vertex and platform access | Package-specific open-source licenses plus Google Cloud service terms | Python dependencies and remote services | Conditional | Verify every exact package and transitive license in the lock; accept and recheck service terms. |
| Pydantic | Strict typed contracts | MIT | Python dependency | Approved candidate | Pin exact version and transitive graph; preserve notice. |
| FastAPI | API edge candidate | MIT | Python dependency and container | Approved candidate, not architecture-selected | Confirm under implementation design; pin exact version and transitive graph. |
| `llama.cpp` | Local Gemma inference runtime candidate | MIT | Local binary or locally built runtime | Approved candidate | Pin source/release and hash; review build dependencies; isolate runtime. Runtime license does not cover weights. |
| Gemma model artifacts: Ollama `gemma4:e4b-it-qat`, Q4_0, upstream `google/gemma-4-E4B-it-qat-q4_0-gguf` | Residual identifier span proposals inside the laboratory privacy boundary | Apache-2.0, as declared by the publishing repository and confirmed by the owner on 2026-08-22 | Separately downloaded local Ollama blob; never committed, containerised, or deployed to a cloud runtime | Approved for the local privacy lane | Before measurement, record the upstream repository, revision, file name, artifact SHA-256, and immutable Ollama blob digest in the P1 evidence manifest; keep model material under ignored local storage; synthetic corpus only; no clinical or workflow decision; the model proposes spans and never approves, redacts, or releases anything. |
| Gemini on Google Cloud | Agent reasoning in contest path | Google Cloud agreement and Service Specific Terms | Remote managed service | Conditional, non-clinical only | Synthetic non-clinical research prototype; no clinical-production claim; terms recheck at freeze and submission. |
| Gemini Enterprise Agent Platform components | Runtime, Registry, governed extensions, and observability | Google Cloud agreement, service terms, and product-specific documentation | Remote managed services | Conditional | Billing/access smoke, region and Pre-GA status, exact service terms, outage contract, and no regulated data in unsupported Pre-GA services. |
| ClinVar | Public variant evidence and historical replay | NCBI/ClinVar data policy | Live retrieval and attributed captured replay | Conditional | Provenance, weekly-release/retrieval date, attribution, professional-review disclaimer, and no direct diagnostic-use claim. |
| NCBI E-utilities and PubMed metadata | Literature discovery and citation metadata | NCBI usage policy plus third-party abstract copyright | Live retrieval and exact ESummary bibliographic capture | Conditional | Protocol 1.0.1 stores ESummary JSON only, with no abstract or full text; implementation must configure `tool`/`email`, rate limits, and visible disclaimer. |
| NCBI GEO `GSE248438` | Exact public BRCA2 functional-data row and chronology metadata for RCL-205 captured replay | NCBI GEO public data service and record-level provenance | Exact XLSX and brief SOFT bytes under attributed capture | Approved for RCL-205 frozen source package; product implementation conditional | Preserve accession, official locators, byte hashes, source columns, as-captured row limitation, and non-clinical disclaimer; fail on retrieval/hash mismatch. |
| Nature DOI `10.1038/s41586-024-08349-1` | Publication-to-GEO accession linkage for RCL-205 | Publisher copyright and public article locator | Fifteen-word Data availability excerpt plus DOI/PMID/accession metadata only | Approved for minimal protocol 1.0.1 linkage capture | No article, abstract, figure, table, or supplementary redistribution; preserve source section, locator, retrieval time, transformation, and short-excerpt boundary. |
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
