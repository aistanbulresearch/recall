# License and Terms Source Notes

- Task: RCL-102
- Reviewed: 2026-08-15
- Purpose: authoritative source map for engineering policy

These notes summarize the terms relevant to the planned architecture. They are not legal advice and do not replace the controlling text.

## Software components

### Contest repository-license requirement

- Source: owner-supplied official Rules snapshot, SHA256 `85313D6B799DB5E5E308949C2F035E8D3A22B9AA1377C2AD86D68DEC16DFD3A2`
- Relevant sections: Project Requirements lines 91 through 105; Intellectual Property Rights lines 376 through 400.
- Observed:
  - no specific repository license and no open-source-publication requirement is imposed;
  - open-source software is permitted when its licenses are followed and the submission adds its own functionality;
  - third-party SDKs, APIs, data, and information require authorization under their applicable terms;
  - the entrant must own the submitted work and necessary rights.
- Recall consequence: Apache-2.0 is permitted. It does not replace the separate license and terms obligations of dependencies, models, APIs, data, or assets.

### Google Agent Development Kit

- Source: <https://github.com/google/adk-python>
- Observed: the official repository identifies the project as Apache-2.0 licensed.
- Recall consequence: allowed candidate after exact version, transitive dependency, and notice verification.

### Pydantic

- Source: <https://github.com/pydantic/pydantic>
- Observed: the official repository identifies the project as MIT licensed.
- Recall consequence: allowed candidate after exact lock and transitive review.

### FastAPI

- Source: <https://github.com/fastapi/fastapi>
- Observed: the official repository and project metadata identify the project as MIT licensed.
- Recall consequence: allowed candidate only if selected by the API/web design; this note does not select it.

### llama.cpp

- Source: <https://github.com/ggml-org/llama.cpp/blob/master/LICENSE>
- Observed: the runtime source uses the MIT license.
- Recall consequence: runtime rights and model-weight rights remain separate. An approved runtime does not approve a Gemma artifact.

## Gemma

### Terms of Use

- Source: <https://ai.google.dev/gemma/terms>
- Page last modified: 2026-04-01
- Observed:
  - Gemma uses custom terms rather than a standard permissive open-source license.
  - Making Gemma functionality available as a hosted service is treated as distribution.
  - Distribution requires downstream restrictions and copies/notices defined by the terms.
  - Outputs are not model derivatives, and Google states that it claims no rights in generated outputs.
- Recall consequence: weights are conditional local artifacts and are not committed, released, or baked into public images.

### Prohibited Use Policy

- Source: <https://ai.google.dev/gemma/prohibited_use_policy>
- Page last updated: 2024-08-05 at review time
- Observed: the policy prohibits unlicensed professional practice, automated decisions in healthcare and other high-impact domains, misleading capability claims, and processing sensitive information without required rights and consent.
- Recall consequence: Gemma is limited to residual identifier span proposals. Deterministic code owns redaction and egress, and the contest uses synthetic data.

## Google Cloud and Gemini services

- Source: <https://cloud.google.com/terms/service-terms>
- Retrieved: 2026-08-15
- Observed:
  - current terms identify prompts and generated output as Customer Data and state that Google does not train or fine-tune AI/ML models on Customer Data without permission or instruction;
  - Generative AI Services may be inaccurate and are not designed to satisfy the customer's regulatory or legal obligations;
  - Generative AI Services are prohibited for clinical purposes, as a substitute for professional medical advice, or where regulatory clearance is required;
  - Pre-GA offerings should not process personal or regulated data unless specific written terms allow it;
  - customers remain responsible for agent actions, fitness, access authorization, judgment, and supervision.
- Recall consequence: the hackathon deployment is a non-clinical research prototype using synthetic institutional records and public evidence. Future clinical deployment is blocked pending a separate terms and regulatory review. De-identification alone does not cure a purpose restriction.

## NCBI, ClinVar, and PubMed

### ClinVar use policy

- Source: <https://www.ncbi.nlm.nih.gov/clinvar/docs/maintenance_use/>
- Retrieved: 2026-08-15
- Observed:
  - ClinVar data is updated weekly;
  - NIH does not independently verify submitted information;
  - the content is not intended for direct diagnostic or medical decision use without genetics-professional review;
  - ClinVar requests attribution when its data is copied or distributed.
- Recall consequence: capture release/retrieval provenance, display attribution and limitations, retain human authority, and never treat availability as verification.

### NCBI website and E-utilities policy

- Source: <https://www.ncbi.nlm.nih.gov/home/about/policies/>
- Supporting E-utilities documentation: <https://www.ncbi.nlm.nih.gov/books/NBK25497/> and <https://www.ncbi.nlm.nih.gov/books/NBK25499/>
- Retrieved: 2026-08-15
- Observed:
  - E-utilities clients should use the documented endpoint and identify the tool and contact email;
  - the baseline limit is no more than three requests per second without an API key;
  - NCBI's disclaimer and copyright notice must be evident to product users;
  - NLM does not claim PubMed abstract copyright, but publishers or authors may hold it.
- Recall consequence: rate-limit and identify the connector, display required notices, and avoid redistributing full abstracts or full text without verified rights.

## Required rechecks

- At RCL-301: exact package versions, transitive licenses, model source/hash, and container base terms.
- At feature freeze: Google Cloud, Gemma, NCBI, and ClinVar pages plus all selected UI and asset licenses.
- Before submission: any contest disclosure or license wording tied to the final distributed repository and demo.
