# The policy is the intent. The behaviour is the fact.

- Status: **DRAFT for owner review.** Not published.
- Date: 2026-08-25
- Lane: L3
- Sources: the citation table below. The Mersch et al. figures, PMID 30264118,
  were verified against the live record on 2026-08-25, cohort size and testing
  window from the abstract's results sentence; the remaining table entries carry
  their identifiers and have not been re-pulled since. Measured captures from
  `artifacts/evidence/**`; frozen figures from
  `artifacts/evidence/p1-frozen-001/p1-frozen-001.corrected-view.json`
- Every number below was read from its artifact while writing this draft, not
  from memory.

---

## A result that means wait

When a genetic test cannot yet interpret a variant, the lab files it as a
variant of uncertain significance. The clinical meaning of that phrase is: do not
act, wait for evidence.

It is not a rare filing and it does not stay put. In the largest published
cohort, one commercial laboratory and 1.45 million individuals tested from 2006
through 2018, 24.9% of reported uncertain variants were later reclassified, and
for those upgraded to pathogenic or likely pathogenic the median time to an
amended report was 1.86 years (Mersch et al., JAMA 2018, PMID 30264118,
[DOI](https://doi.org/10.1001/jama.2018.13152)).

Reclassification is not paperwork. When laboratories resolved uncertain variants
with additional evidence, surveyed clinicians reported changed clinical
management for 44% of affected patients and 78% of families (Karam et al., JAMA
Network Open 2019, PMID 31642931,
[DOI](https://doi.org/10.1001/jamanetworkopen.2019.13900)).

The evidence that resolves these cases is increasingly systematic laboratory
measurement. A 2025 study integrating functional assays into the ACMG framework
reclassified 90% of the assessed uncertain ATM variants (Hanenberg et al.,
Clinical Cancer Research 2025, PMID 40105422,
[DOI](https://doi.org/10.1158/1078-0432.CCR-24-3936)). The field knows
reevaluation is needed; the ACMG has issued a formal statement on the
reevaluation and reanalysis of genomic test results (Deignan et al., Genetics in
Medicine 2019, PMID 31015575,
[DOI](https://doi.org/10.1038/s41436-019-0478-1)).

What no guideline provides is a mechanism that watches the evidence itself.
Records get diffed. Evidence goes unwatched.

If you maintain software, you already know this shape. You monitor dependencies
for CVEs. Imagine alerts firing only when the vendor updated the changelog, never
when the exploit went public. That is the current posture in clinical genetics,
and one real variant measures what it costs: the laboratory's data deposit went
public on GEO on 2024-09-27; first ClinVar-record reflection followed on
2026-04-25, **575 days by registry chronology**. Our preregistered lead-time
metric, counted from the qualifying publication, is **472 days**.

---

## What we built

Recall is a fleet of specialist agents that watch public evidence for variants a
laboratory has already reported as uncertain. One agent watches evidence. One
assesses it. One audits every citation, because models invent them. The agent
that proposes is never the agent that checks.

The controller delegates the work. **Decisions stay in deterministic policy.** No
model classifies a variant, changes a report, or contacts a patient. When the
evidence is too weak, the system abstains rather than guessing, and says so.

Stack: Gemini 3.7 Flash, Google ADK, Vertex AI Agent Engine, and a local Gemma 4
for redaction.

---

## The finding that changed how we test everything

We removed an IAM binding from a service account. The control plane confirmed it.
We read the policy back, which is stronger than trusting the remove call, and the
read-back agreed: the binding was gone.

Then we measured what the credential could actually do.

> The policy read-back reported the binding removed while impersonation STILL
> SUCCEEDED for four further attempts; the mint was refused on the fifth. Grant
> propagation showed the same lag in reverse: the binding was present for two
> attempts before a token could be minted.

Four successful uses of a privilege the control plane had already reported as
revoked. The reverse direction had the same lag: two attempts where the grant
existed on paper and did not yet work.

The conclusion we wrote into the artifact:

> A revoked binding is not immediately an unusable one. The policy is the intent;
> the behaviour is the fact, and only the behaviour closes the privilege window.

This is not a cloud-provider complaint. Eventual consistency in a distributed
authorization system is expected and documented. The finding is about what counts
as evidence. A revocation confirmed by read-back is a **control-plane assertion
standing in for behaviour**, and we had been treating that class of assertion as
proof throughout. The test that closes the window is the one that presents the
credential and reads the HTTP status: a well-formed request from a principal with
no grant, expecting 403 and observing 403.

---

## Observing the observability

Here is the part that generalises, and it is the reason this post exists rather
than a feature list.

Once we started measuring behaviour instead of configuration, **the instruments
failed exactly the way the systems did.**

The tracing layer told the same kind of lie. The managed runtime did not
propagate the caller's `traceparent` into the agent container: a caller-minted
trace ID returned 404 from deterministic `traces.get` read-back for three
minutes. Had we trusted the console view, we would have claimed cross-layer trace
parentage we could not demonstrate.

Then the checks themselves. Four separate verification instruments in the
platform lane were found reading the wrong surface: a guard searching a `repr`, a
classifier reading silence as success, a redactor rewriting numbers inside JSON,
and an acceptance criterion that passed as `0 == 0` on an empty set. Every one
reported green. Every one was caught by running it against reality and reading
raw output rather than the verdict.

Our own evidence pipeline was no better. Declared hashes for a frozen measurement
were computed over the bytes on disk while git stored line-ending-normalised
blobs, so a fresh checkout could not reproduce a single declared hash. The
content was intact and no hash was miscomputed; what was broken was
reproducibility, and the warning had been printing on every commit for two days
where it read as platform noise. Another lane's integration gate caught it, not
us.

The pattern is one sentence: **a warning, an estimate, or a safeguard feels like
overhead exactly when you are busiest with the thing it is about.** A verdict is
not a measurement. An empty result is not a clean result. And when two
measurements disagree, the work is finding which one is lying, not keeping the
one that fits.

We ended up writing that down as standing rules, because discovering it five
times was expensive. The rules are in the repository, and the honest note about
them is that every single one has a defect of our own as its source.

---

## What the privacy boundary actually does

Institutional prose never leaves the laboratory. Not "is redacted before it
leaves": never leaves, because the cloud-bound payload declares no free-text
field at all. Detectors run, a local Gemma proposes residual identifier spans,
and deterministic adjudication decides. The model can only propose. It never
approves, redacts, or releases anything.

The measured result on a frozen, preregistered synthetic corpus of 180 records:

| | Value |
|---|---|
| Exact recall, deterministic baseline | 0.760648 |
| Exact recall, with adjudicated local-model spans | 0.978241 |
| Accepted payloads, baseline | 0 of 180 |
| Accepted payloads, primary arm | 136 of 180 |
| Incremental true positives from the local model | 470 |
| Accepted identifier escapes, every path | **0** |

Two things about that table are worth more than the numbers.

The run was **preregistered**: the prediction was committed 45 seconds before the
run started, and the commit is in the history. We said in advance what would
count as success and what would falsify it.

And we published the arm that failed. The model's own character offsets
contributed **zero** incremental true positives and added **903** false
positives. Only the surface strings it returned, placed by deterministic exact
search, were worth anything. Both arms are in the report. The failing one is not
in a footnote.

---

## Honesty boundaries

- All institutional records in this work are synthetic. No real patient data was
  used at any point.
- Privacy results describe one synthetic corpus. They are not a
  de-identification, clinical, or regulatory claim, and no real-data performance
  is implied.
- Two intervals are reported for one real variant and they are not
  interchangeable. 575 days is registry chronology, from the GEO accession
  becoming public to the ClinVar-record reflection. 472 days is the
  preregistered lead-time metric, counted from the qualifying publication. The
  aggregate ClinVar record became **conflicting, not uniformly pathogenic**, and
  the chronology **does not establish that the paper caused the later
  submission**.
- Structured-only egress acceptance is a property of the payload shape, not a
  detection result, and is never reported as detector or model performance.
- Recall is a non-clinical research prototype. It creates simulated review tasks
  for a specialist. It does not make clinical decisions, and a human makes the
  final call on every one.
- The platform artifacts measure a running service. They say nothing about
  whether the code that produced them is present on any integrated branch, which
  is measured separately.

---

## Citation table

Verified against live PubMed records on 2026-08-25.

| Claim | Source | PMID | DOI |
|---|---|---|---|
| 24.9% of reported VUS reclassified; upgrade median 1.86 y | Mersch et al., JAMA 2018;320(12):1266-1274 | 30264118 | [10.1001/jama.2018.13152](https://doi.org/10.1001/jama.2018.13152) |
| Reclassification changed management: 44% patients / 78% families | Karam et al., JAMA Netw Open 2019;2(10):e1913900 | 31642931 | [10.1001/jamanetworkopen.2019.13900](https://doi.org/10.1001/jamanetworkopen.2019.13900) |
| ACMG statement on reevaluation and reanalysis | Deignan et al., Genet Med 2019;21(6):1267-1270 | 31015575 | [10.1038/s41436-019-0478-1](https://doi.org/10.1038/s41436-019-0478-1) |
| Functional assays reclassified 90% of assessed ATM VUS | Hanenberg et al., Clin Cancer Res 2025;31(12):2426-2440 | 40105422 | [10.1158/1078-0432.CCR-24-3936](https://doi.org/10.1158/1078-0432.CCR-24-3936) |

One qualifier the cohort data deserves: most VUS reclassifications are downgrades
to benign, 91.2% in that cohort. The upgrades are the rare, high-stakes tail.
Recall exists for that tail.

---

## Build details

Architecture, including the agent topology and the deterministic control path:
[`docs/architecture/TARGET_ARCHITECTURE.md`](docs/architecture/TARGET_ARCHITECTURE.md).
Agent runtime versions are pinned rather than floating, so a run can be
reproduced against the same stack: `google-adk==2.7.1` and
`google-cloud-aiplatform[agent_engines]==1.165.1`.

---

## About

Recall was built for the **All Things Agentic Hackathon**.

- Devpost: _link added when the repository goes public_
- Repository: _link added when the repository goes public_
- Follow the build: **#AllThingsAgenticHackathon**
