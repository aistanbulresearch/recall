# RCL-205 Historical Replay Case

- Status: protocol 1.0.1 source package verified offline; product execution not started
- Frozen source package: 2026-08-16T23:19:30Z
- Data modes: `CAPTURED_REPLAY` for the historical package, `SYNTHETIC` for institutional cases, and a separate `LIVE_PUBLIC` connector smoke
- Scope: non-clinical research prototype only
- Source manifest: `HISTORICAL_REPLAY_SOURCE_MANIFEST.json`
- Candidate ledger: `HISTORICAL_REPLAY_CANDIDATE_LEDGER.md`
- Verification report: `reports/2026-08-17--rcl-205-protocol-1.0.1-verification.md`

## Claim boundary

This package preregisters one bounded historical example. It does not prove clinical validity, general lead time, causation between a publication and a submitter's later classification, or performance across all genes, variants, laboratories, and evidence types.

Recall never classifies this variant. The expected product output is an audited simulated review-priority signal for a synthetic institutional case. A clinician remains the final authority.

## Frozen positive case

| Field | Frozen value |
|---|---|
| Gene | `BRCA2` |
| Variant | `NM_000059.4:c.7522G>C` |
| Protein | `NP_000050.2:p.Gly2508Arg` / `G2508R` |
| Genomic | `NC_000013.11:g.32356514G>C` |
| ClinVar Variation ID | `2895953` |
| ClinVar VCV | `VCV002895953` |
| Qualifying evidence | Sahu et al., *Nature* 2025, DOI `10.1038/s41586-024-08349-1`, PMID `39779848` |
| Exact-row verification | NCBI GEO `GSE248438_SGE_BRCA2_results.xlsx`, `GSE248438` |
| Later corroborating paper | Huang et al., *Nature* 2025, DOI `10.1038/s41586-024-08388-8`, PMID `39779857` |

### Why this case qualifies

1. `VCV002895953.1` and `VCV002895953.4` report an aggregate germline interpretation of uncertain significance.
2. Sahu et al. was published on 2025-01-08 and reports saturation genome editing across BRCA2 exons 15 through 26.
3. The official NCBI GEO result file contains the exact `c.7522G>C / G2508R` row in exon 15.2 with source classification `Pathogenic Strong`, function score `-1.44817784674576`, and probability `0.999500335148772`.
4. `VCV002895953.4` remained aggregate VUS when updated on 2026-04-13.
5. `VCV002895953.5` adds a likely-pathogenic Ambry submission first present in ClinVar on 2026-04-25. That submission cites Sahu et al. (PMID `39779848`) only. Huang et al. (PMID `39779857`) is retained separately as corroborating literature and is not represented as an Ambry-submission citation. The aggregate record becomes conflicting, not uniformly pathogenic.

The source chronology supports a narrower statement: a material exact-variant functional signal was publicly available before a later likely-pathogenic ClinVar submission appeared. It does not establish that the paper caused the later submission.

## Frozen timeline and derived intervals

| Event | Source date | Meaning |
|---|---:|---|
| GEO submission | 2023-11-22 | Dataset submission date, not public availability |
| GEO public | 2024-09-27 | Dataset accession became public; exact later-captured XLSX row state is not inferred for this date |
| ClinVar v1 baseline | 2024-11-10 | Aggregate VUS with two VUS submissions |
| Qualifying peer-reviewed evidence | 2025-01-08 | Sahu et al. publication date |
| Later evaluator date | 2026-02-03 | Date evaluated on the later likely-pathogenic submission |
| ClinVar v4 comparison | 2026-04-13 | Aggregate remains VUS |
| ClinVar v5 public appearance | 2026-04-25 | Likely-pathogenic submission first present; aggregate becomes conflicting |
| GEO last update as captured | 2026-07-29 | Current record metadata; not the qualifying publication date |
| Exact XLSX capture | 2026-08-16T23:18:35Z | Exact workbook bytes and row are verified only as captured |

Derived from these exact dates:

- qualifying publication to later evaluator date: `391` calendar days;
- qualifying publication to later public ClinVar appearance: `472` calendar days.

Only the `472`-day interval is the preregistered public-source lead-time metric. It is reported for this case only. The `391`-day interval is contextual and must be labeled separately.

The GEO record currently links PMID `41957374`; the qualifying Nature publication is PMID `39779848`. The offline linkage predicate verifies PMID `39779848`, its DOI, the Nature Data availability statement naming `GSE248438`, contributor/scope consistency, and the exact captured workbook row. It never requires current GEO PMID equality.

The demo may compress these source events into accelerated Week 0, Week 3, and Week 6 stages. Every screen must say that the weeks are accelerated replay stages and must retain the actual source dates.

## Frozen negative controls

The controls test exact source-to-variant attribution. They are not claims that the variants are benign, permanently unchanged, or unsupported by all other evidence.

| Control | ClinVar anchor | Reason it is negative for the Sahu evidence event | Expected replay result |
|---|---|---|---|
| `BRCA2 NM_000059.4:c.425+3A>G` | `VCV000495460.24`, Variation ID `495460` | Intronic variant outside the paper's exons 15 through 26 assay scope; no exact-row match | `CandidateDeltaReceipt: ABSENT`; deterministic `NO_ACTION` if all base receipts are complete |
| `BRCA2 NM_000059.4:c.1315T>G (p.Phe439Val)` | `VCV000051100.33`, Variation ID `51100` | Exon 10 missense variant outside the paper's exons 15 through 26 assay scope; no exact-row match | `CandidateDeltaReceipt: ABSENT`; deterministic `NO_ACTION` if all base receipts are complete |

A gene-only matcher would falsely attach the BRCA2 study to both controls. Recall must require exact normalized allele matching plus source-scope compatibility.

## Preregistered expected signal

### Positive route

1. Watcher observes the qualifying 2025 publication metadata and associated approved dataset.
2. Deterministic normalization matches the exact transcript/genomic allele, declared source scope, complete snapshot, and new observation hash to the synthetic `WatchCase`, producing `CandidateDeltaReceipt: PRESENT`.
3. Evidence Assessor may propose a material functional-evidence delta from that receipt. It may not suppress the route, classify the variant, select `NO_ACTION`, or create a task.
4. Citation Auditor independently verifies PMID, DOI, source scope, exact allele, and the captured source hash.
5. Policy Gate receives complete authoritative receipts and is expected to emit `REVIEW_REQUIRED` for the synthetic case.
6. Transactional task creation is expected to create exactly one simulated review task.

### Negative routes

For each negative control, the same source event is ingested. Exact allele and scope matching must reject attribution. With complete audit and policy inputs, expected deterministic outcome is `NO_ACTION`, with zero review tasks.

An unavailable source, hash mismatch, missing exact allele, incomplete audit, or uncertain normalization cannot be converted into a clean negative. It must produce the applicable typed failure, `ABSTAIN`, or technical `HALTED` state under the frozen authority rules.

## Data-mode plan

| Surface | Mode | Rule |
|---|---|---|
| Institutional watch records | `SYNTHETIC` | No real patient or laboratory record is used |
| Historical source timeline | `CAPTURED_REPLAY` | Exact source versions, dates, locators, and hashes come from the frozen manifest |
| Current ClinVar connector smoke | `LIVE_PUBLIC` | Labeled separately; validates connectivity only and cannot replace the replay |
| Unit/interface substitutions | `MOCK` | Cannot satisfy route-validity or product-performance evidence |

## Offline capture integrity

Protocol 1.0.1 stores ten permitted source artifacts under `artifacts/evidence/rcl-205/`. Every captured source records an exact repository-relative path, retrieval timestamp, byte count, SHA-256 over unnormalized bytes, semantic anchor, media type, transformation, and redistribution boundary.

PubMed uses ESummary bibliographic JSON rather than EFetch XML so no abstract or full text is captured. Nature is limited to a 15-word Data availability linkage excerpt. The current ClinVar connector remains a separate `LIVE_PUBLIC` source with no frozen expected hash.

Offline verification commands:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\evidence\verify-rcl-205-captures.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\evidence\test-rcl-205-captures.ps1
```

The verified package contains 10 captures and 1,400,869 bytes, with one exact matching XLSX row. The clean-copy test passes, one mutated byte fails with `hash_mismatch`, a path escaping the declared capture root fails, and verification performs zero network calls.

## Success and failure gates

The RCL-205 source-package gate is locally verified under protocol 1.0.1. The later product evaluation passes only if:

- the preregistered positive is detected under the frozen rule;
- both negative controls produce deterministic `ABSENT` candidate receipts without invoking Assessor or Auditor;
- every result includes source coverage, retrieval completeness, exact hashes, and activation counters;
- no missing or mismatched input is presented as clean;
- no fixture name, route, timer, or preset selects an outcome;
- failed results remain recorded and no replacement case is chosen after observing product performance without a new protocol version.

## Measurement-before-build gate

| Gate | Result | Evidence |
|---|---|---|
| O1 prior signal | Pass | Versioned ClinVar history, peer-reviewed publication, and exact official GEO row establish the bounded signal |
| O2 capability and data | Pass for frozen source package | Ten exact repository captures, semantic versions, rights boundaries, corrected chronology/linkage, one exact row, and two controls verify offline; product connector remains unimplemented |
| O3 route validity | Not yet tested | RCL-503 must execute the minimal real captured route; mocks cannot satisfy this gate |
| O4 measurement cost | Pass for the bounded package | One positive, two controls, one live smoke, and hash verification fit the contest budget |

Decision: proceed to Phase 2 package audit. Do not claim product detection until RCL-503 and RCL-801 execute the frozen protocol.

## Rights and provenance

- ClinVar data is used through exact accessions and versions with NCBI attribution. ClinVar asks users to cite the accession and version and provides archived releases and version retrieval.
- NCBI GEO supplies the exact public result dataset. The repository records its accession, locator, retrieval hash, and only the minimum derived row required by the replay design.
- PubMed ESummary JSON is used as bibliographic metadata. No abstract or full article is copied into the repository.
- Nature article text and supplementary files are not redistributed. One 15-word Data availability linkage excerpt is retained with DOI, PMID, section, retrieval time, and explicit rights boundary; the exact functional row is verified against the official NCBI GEO deposit.
- Implementation must comply with NCBI rate limits and include a descriptive `tool` and contact `email` for E-utilities.

Official policy references:

- <https://www.ncbi.nlm.nih.gov/clinvar/docs/maintenance_use/>
- <https://www.ncbi.nlm.nih.gov/clinvar/docs/downloads/>
- <https://www.ncbi.nlm.nih.gov/clinvar/docs/help/>
- <https://www.ncbi.nlm.nih.gov/clinvar/docs/faq/>
- <https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE248438>

## Known limitations

- This is one intentionally bounded case and cannot estimate population-wide or laboratory-wide lead time.
- ClinVar is an archive of submitter assertions; aggregate classifications and dates must be described precisely.
- The later likely-pathogenic submission cites the 2025 studies, but the chronology does not prove causation.
- Repository hashes identify the exact captured bytes. Dynamic HTML can change while a VCV accession version remains semantically stable; the accession and version are the primary semantic anchors, while the hash proves only capture integrity.
- The Springer Nature supplementary download returned an automated client-challenge page in this environment. It is excluded from evidence. Exact-row verification instead uses the official NCBI GEO deposit.
- No Recall connector, agent route, policy execution, web rendering, or empirical detection result exists yet.
