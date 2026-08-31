# RCL-205 Historical Replay Candidate Ledger

- Status: frozen before product execution
- Date: 2026-08-16
- Protocol: `EVALUATION_PROTOCOLS.md`, Protocol P5

This ledger records every candidate materially screened during RCL-205. Selection was completed before Recall executed any historical replay, preventing outcome-driven case replacement.

## Positive-candidate screening

| Candidate | Source checked | Decision | Reason |
|---|---|---|---|
| `BRCA2 NM_000059.4:c.7522G>C (p.Gly2508Arg)` | ClinVar `VCV002895953.1`, `.4`, `.5`; Sahu PMID `39779848`; Huang PMID `39779857`; GEO `GSE248438` | Selected | Exact GEO row exists; aggregate ClinVar remains VUS through v4; v5 later adds a likely-pathogenic submission that cites the 2025 studies |
| `BRCA2 NM_000059.4:c.7876T>C (p.Trp2626Arg)` | ClinVar `VCV000429208.15`; RCV `RCV000493105.1` | Rejected | Likely-pathogenic assertion was already evaluated in 2014, so the 2025 publication does not provide the required VUS-before-later-update contrast |
| `BRCA1 NM_007294.4:c.132C>T (p.Cys44=)` | ClinVar `RCV000217253.1` and `RCV000258218.1` | Rejected | Condition-level records already include a pathogenic assertion evaluated in 2015; no clean evidence-before-later-classification sequence for the proposed later study |
| `FBN1 NM_000138.5:c.1006T>C (p.Cys336Arg)` | ClinVar Variation ID `548997`; `RCV000663435.1` | Rejected | A likely-pathogenic assertion was evaluated in 2017, before the later paper lead considered during screening |

Rejected candidates remain in the ledger. They cannot be silently substituted after Recall's output is observed.

## Negative-control screening

| Candidate | Decision | Frozen role | Reason |
|---|---|---|---|
| `BRCA2 NM_000059.4:c.425+3A>G` | Selected | Negative control 1 | Same gene, but outside exons 15 through 26 and absent from the exact SGE row set; tests gene-only false attribution |
| `BRCA2 NM_000059.4:c.1315T>G (p.Phe439Val)` | Selected | Negative control 2 | Same gene and variant type, but exon 10 is outside the source scope; tests scope and exact-allele matching |
| Unrelated-gene control | Rejected for minimum set | Optional later extension | Too easy for the minimum proof; same-gene controls are more discriminating |

## Freeze rule

The selected positive and controls are immutable for protocol version `1.0.0`. If implementation reveals a source defect, report the failed case and open a new protocol version with a reason before selecting any replacement. A model or agent may not choose the evaluation case.

## Source locators

- Positive ClinVar: <https://www.ncbi.nlm.nih.gov/clinvar/variation/2895953/>
- Positive paper: <https://doi.org/10.1038/s41586-024-08349-1>
- Exact official dataset: <https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE248438>
- Rejected BRCA2 candidate: <https://www.ncbi.nlm.nih.gov/clinvar/variation/429208/>
- Rejected BRCA1 records: <https://www.ncbi.nlm.nih.gov/clinvar/RCV000217253.1/> and <https://www.ncbi.nlm.nih.gov/clinvar/RCV000258218.1/>
- Rejected FBN1 candidate: <https://www.ncbi.nlm.nih.gov/clinvar/variation/548997/>
- Negative control 1: <https://www.ncbi.nlm.nih.gov/clinvar/variation/495460/>
- Negative control 2: <https://www.ncbi.nlm.nih.gov/clinvar/variation/51100/>
