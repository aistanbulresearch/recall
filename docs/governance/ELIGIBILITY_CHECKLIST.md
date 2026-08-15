# Recall Eligibility Checklist

- Status: verified, final live-Rules recheck remains a submission gate
- Review date: 2026-08-15
- Task: RCL-101
- Category target: Fortified Enterprise Fleet
- Canonical source notes: [`ELIGIBILITY_SOURCE_NOTES.md`](ELIGIBILITY_SOURCE_NOTES.md)

## Gate summary

Recall may continue through architecture and technical design. The owner has confirmed all personal eligibility and authority requirements and will enter as an individual/solo participant. Product implementation must not begin until the dependency/license policy is closed. Billing-dependent verification remains paused separately.

## Requirements

| Requirement | Status | Evidence or action |
|---|---|---|
| Project created during Submission Period | met | First repository commit: 2026-08-14; period began 2026-08-03. |
| Submitted work built during Submission Period | met so far, continuous gate | Tracked product-code files: 0; implementation has not started. Preserve commit provenance. |
| Independent original work | met so far, continuous gate | DEC-2026-08-15-014 prohibits direct component or artifact copying. |
| Pre-existing work incorporated | none on current facts | No prior component is imported. Abstract pattern and failure-mode inspection does not incorporate code or work into Recall. If this changes, stop and reassess. |
| Gemini 3.5 or newer | planned, not verified | Mandatory cloud smoke awaits billing. |
| Listed Google agent framework | local capability passed, deployment unverified | ADK import passed; managed execution awaits billing. |
| Google Cloud infrastructure service | planned, not verified | Firestore, Pub/Sub, and Cloud Run path awaits billing. |
| Fortified Fleet behavior | design accepted, execution unverified | Registry, weeks-long context, governance, and telemetry require working proof. |
| Installation and reproducibility | not started | README spin-up and clean-clone evidence required. |
| Test access through Judging Period | not started | Prefer public hosted demo and public repository before submission. |
| English application and materials | planned | English is the repository and submission language. |
| Third-party SDK/API/data rights | pending RCL-102 | Create dependency, license, terms, and data-source inventory before implementation. |
| Hosted URL | not started | Highly encouraged and required by Recall's demo plan. |
| Repository URL | met for development, final access pending | Private repository exists; public visibility is preferred by judging criteria. |
| Architecture diagram | not started | Must map actual deployed components, not planned-only services. |
| Video at most four minutes | not started | Public YouTube/Vimeo, English or subtitled, with visible Google Cloud backend proof. |
| Owner personal eligibility | met by owner attestation | Owner confirmed age/residence/sanctions eligibility and no prohibited Contest Entity, government, or conflict status. No sensitive personal detail is persisted. |
| Entry capacity and consent | met | Entry capacity is `individual/solo`; owner confirmed authority to use the `aistanbulresearch` identity and repository. |

## Independent implementation interpretation

The disclosure trigger applies to pre-existing code or work incorporated into the submission. Recall currently incorporates none. Inspecting a separate system to identify abstract engineering patterns, failure modes, or acceptance-test questions does not itself import that system into Recall. This interpretation remains valid only while the repository boundary in DEC-2026-08-15-014 is enforced.

Do not add a voluntary public `pre-existing work` section. If Devpost presents an explicit mandatory field, review its exact wording before answering truthfully and narrowly.

## Ambiguities and risks

| Risk | Severity | Response |
|---|---|---|
| Live Rules page could not be fetched independently | High | Recheck Devpost before implementation freeze and final submission. |
| Category names differ from category-specific judging labels | Medium | Enter Fortified Enterprise Fleet; map evidence to the Multi-Agent judging language without claiming formal equivalence. |
| Enterprise Agent Platform list is recommended but not a binding bonus | Medium | Use Runtime and Registry for architectural proof; do not claim bonus points for deployment. |
| Category asks about production data while Recall prohibits patient data | High | Demonstrate the governed production-data boundary using synthetic, captured replay, and live public data; never imply real patient data was used. |
| Private repository is allowed for testing but public documentation is scored | High | Make the repository public before submission only after secret, license, history, and privacy audit. |
| Sponsor-provided contest credits and the preferential-support clause coexist | Low | Treat generally offered contest credits as the stated access mechanism; retain the form/email record and do not claim special sponsorship. |
| Rules require originality and sole ownership | Critical | Maintain repository-local requirements, tests, implementation, provenance, and dependency rights. |

## Owner confirmations recorded

On 2026-08-15, the owner confirmed that the entrant:

1. is above the age of majority and not resident or ordinarily resident in an excluded or sanctioned jurisdiction;
2. is not a prohibited Contest Entity employee/contractor, immediate family/household member, government employee, or other conflict case;
3. will enter as an individual, team, or organization, with the required representative and consent;
4. has authority to use the `aistanbulresearch` organization identity and repository for the submission.

## Decision

`PASS`.

- Architecture, contracts, evaluation, and demo-storyboard work may continue.
- Product implementation waits only for RCL-102 and the remaining technical design gates, not for personal eligibility.
- Cloud deployment evidence waits for billing.
- Any direct import from another project reopens RCL-103 immediately.
- Live Devpost Rules currentness must be rechecked before feature freeze and final submission.
