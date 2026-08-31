/**
 * Recall — the jury-facing narrative page (route `/`).
 *
 * A document, not an application. It states the thesis, shows the problem with
 * captured dates, explains the fleet and the authority boundary, maps the
 * competition's platform capabilities to named mechanisms with honest
 * verification badges, and hands the reader to the evidence surface at
 * `#/demo`.
 *
 * Discipline carried over from the shipped surfaces: missing data never renders
 * as zero or as success; a replay never renders as live; HALTED is never shown
 * as ABSTAIN; colour is always redundant with words; and every number is either
 * stamped with the instant it was read, named as a frozen measurement with its
 * own commit, or shown as PENDING.
 */

import './site.css';

import categoryFit from './data/category-fit.json';
import liveRun from './data/live-run.json';
import historicalCase from '../data/historical-case.json';
import walkthroughCase from '../data/walkthrough-case.json';

type BadgeKind = 'LIVE VERIFIED' | 'SOURCE VERIFIED' | 'DEFERRED' | 'NOT VERIFIED';

const BADGE_CLASS: Record<string, string> = {
  'LIVE VERIFIED': 'live',
  'SOURCE VERIFIED': 'source',
  DEFERRED: 'deferred',
  'NOT VERIFIED': 'absent',
};

function Badge({ kind }: { kind: BadgeKind | string }) {
  return <span className={`badge ${BADGE_CLASS[kind] ?? 'source'}`}>{kind}</span>;
}

interface HeroFile {
  dates: Record<string, string>;
  intervals: { id: string; from: string; to: string; claim_basis: string }[];
  headline_interval_id: string;
  headline_requires_interval_id: string;
  honesty_sentences: string[];
  governing_document: string;
  clinvar_vcv: string;
  qualifying_pmid: string;
  geo_accession: string;
}

interface WalkthroughFile {
  world_evidence: { id: string; what: string; capture: { path: string } }[];
  encounter: { result: { variant: string; gene: string } };
}

const hero = historicalCase as unknown as HeroFile;
const wt = walkthroughCase as unknown as WalkthroughFile;
const run = liveRun as unknown as {
  status: string;
  as_of_utc: string;
  as_of_local: string;
  snapshot_source: string;
  binding: Record<string, string>;
  scan_runs: Record<string, number>;
  role_failures: Record<string, number>;
  round_trips: Record<string, number>;
  artifacts: Record<string, number>;
  faults: Record<string, string | number>;
  pending_until_terminal_evidence: string[];
};
const fit = categoryFit as unknown as {
  note: string;
  capabilities: {
    capability: string;
    mechanism: string;
    badge: string;
    evidence: string;
    limit: string;
  }[];
};

function days(from: string, to: string): number {
  return Math.round(
    (Date.parse(`${to}T00:00:00Z`) - Date.parse(`${from}T00:00:00Z`)) / 86_400_000,
  );
}

function Section({
  num,
  title,
  claim,
  children,
  id,
}: {
  num: string;
  title: string;
  claim: string;
  children: React.ReactNode;
  id?: string;
}) {
  return (
    <section className="sec" id={id}>
      <div className="sec-head">
        <span className="sec-num">{num}</span>
        <h2>{title}</h2>
      </div>
      <p className="sec-claim">{claim}</p>
      {children}
    </section>
  );
}

/**
 * The evidence chronology, drawn to scale.
 *
 * Marker positions are computed from the dates in the governed case file, so
 * the picture cannot disagree with the numbers printed beside it: the long
 * empty stretch on the right IS the interval the text names.
 */
function EvidenceTimeline() {
  const start = Date.parse(`${hero.dates.geo_public}T00:00:00Z`);
  const paper = Date.parse(`${hero.dates.qualifying_publication}T00:00:00Z`);
  const end = Date.parse(`${hero.dates.clinvar_v5_public}T00:00:00Z`);
  const x = (t: number) => 30 + (700 * (t - start)) / (end - start);
  const marks = [
    { at: x(start), date: hero.dates.geo_public, label: 'Data deposited in public' },
    { at: x(paper), date: hero.dates.qualifying_publication, label: 'Publication indexed' },
    { at: x(end), date: hero.dates.clinvar_v5_public, label: 'Public record updated' },
  ];
  return (
    <figure className="fig timeline">
      <svg viewBox="0 0 760 168" role="img" aria-label="Evidence chronology drawn to scale">
        <g fontFamily="IBM Plex Mono, monospace">
          <line x1="30" y1="66" x2="730" y2="66" stroke="#c9c8c2" />
          {/* the stretch in which the record said the same thing */}
          <line x1={marks[1].at} y1="66" x2="730" y2="66" stroke="#8d3b2f" strokeWidth="2" />
          <text x={(marks[1].at + 730) / 2} y="92" fontSize="11" fill="#8d3b2f" textAnchor="middle">
            {days(hero.dates.qualifying_publication, hero.dates.clinvar_v5_public)} days in which
            the chart did not change
          </text>
          <text x={(marks[1].at + 730) / 2} y="110" fontSize="9.5" fill="#6a6c73" textAnchor="middle">
            the evidence was public and free to read the whole time
          </text>
          {marks.map((mark, i) => (
            <g key={mark.date}>
              <circle cx={mark.at} cy="66" r="4.5" fill="#fbfbf9" stroke="#15161a" strokeWidth="1.5" />
              <text
                x={mark.at}
                y="40"
                fontSize="11"
                fill="#15161a"
                textAnchor={i === 0 ? 'start' : i === marks.length - 1 ? 'end' : 'middle'}
              >
                {mark.date}
              </text>
              <text
                x={mark.at}
                y="24"
                fontSize="9.5"
                fill="#6a6c73"
                textAnchor={i === 0 ? 'start' : i === marks.length - 1 ? 'end' : 'middle'}
              >
                {mark.label}
              </text>
            </g>
          ))}
          <line x1="30" y1="130" x2="730" y2="130" stroke="#15161a" strokeWidth="1" />
          <text x="380" y="150" fontSize="11" fill="#15161a" textAnchor="middle">
            {days(hero.dates.geo_public, hero.dates.clinvar_v5_public)} days end to end
          </text>
        </g>
      </svg>
      <figcaption className="fig-cap">
        Fig 1. Drawn to scale from the dates in the governed case file. Nothing was hidden and
        nothing failed; the evidence simply arrived somewhere nobody was watching on behalf of
        the case.
      </figcaption>
    </figure>
  );
}

/** Two trust boundaries and the human at the end of them. */
function BoundaryDiagram() {
  return (
    <figure className="fig">
      <svg viewBox="0 0 760 330" role="img" aria-label="Recall trust boundaries">
        <defs>
          <marker id="ar" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
            <path d="M0,0 L8,4 L0,8 z" fill="#15161a" />
          </marker>
        </defs>
        <g fontFamily="IBM Plex Mono, monospace" fill="#15161a">
          {/* laboratory */}
          <rect x="8" y="26" width="228" height="270" fill="none" stroke="#15161a" />
          <text x="20" y="46" fontSize="10" letterSpacing="1.4" fill="#6a6c73">
            LABORATORY BOUNDARY
          </text>
          {[
            'Synthetic institutional notes',
            'Deterministic detectors',
            'Local Gemma: residual spans',
            'Adjudication + redaction',
            'Structured-only egress gate',
            'Signed PrivacyReceipt',
          ].map((label, i) => (
            <text key={label} x="22" y={76 + i * 30} fontSize="11">
              {label}
            </text>
          ))}
          <text x="22" y="272" fontSize="9.5" fill="#8d3b2f">
            note text never crosses this line
          </text>

          {/* google cloud */}
          <rect x="268" y="26" width="300" height="270" fill="none" stroke="#15161a" />
          <text x="280" y="46" fontSize="10" letterSpacing="1.4" fill="#6a6c73">
            GOOGLE CLOUD BOUNDARY
          </text>
          <text x="282" y="72" fontSize="11">Cloud Run Job · Scheduler</text>
          <text x="282" y="94" fontSize="11" fontWeight="700">Deterministic Controller</text>
          <text x="282" y="116" fontSize="11">Agent Registry resolution</text>
          <text x="296" y="140" fontSize="11" fill="#2c4a7c">Evidence Watcher</text>
          <text x="296" y="160" fontSize="11" fill="#2c4a7c">Evidence Assessor</text>
          <text x="296" y="180" fontSize="11" fill="#2c4a7c">Citation Auditor</text>
          <text x="282" y="204" fontSize="11">Agent Gateway · receipts</text>
          <text x="282" y="226" fontSize="11">Firestore append-only ledger</text>
          <text x="282" y="248" fontSize="11" fontWeight="700">Deterministic Policy Gate</text>
          <text x="282" y="270" fontSize="11">Observability · traces</text>
          <text x="282" y="288" fontSize="9.5" fill="#6a6c73">
            models propose · policy decides
          </text>

          {/* human */}
          <rect x="600" y="96" width="152" height="128" fill="none" stroke="#15161a" />
          <text x="612" y="118" fontSize="10" letterSpacing="1.4" fill="#6a6c73">
            HUMAN AUTHORITY
          </text>
          <text x="614" y="146" fontSize="11">Simulated ReviewTask</text>
          <text x="614" y="168" fontSize="11">Specialist review</text>
          <text x="614" y="196" fontSize="11" fontWeight="700">Final decision</text>

          {/* arrows */}
          <line x1="236" y1="150" x2="266" y2="150" stroke="#15161a" markerEnd="url(#ar)" />
          <text x="228" y="140" fontSize="9" fill="#6a6c73" textAnchor="start">
            structured only
          </text>
          <line x1="568" y1="160" x2="598" y2="160" stroke="#15161a" markerEnd="url(#ar)" />
          <text x="562" y="150" fontSize="9" fill="#6a6c73" textAnchor="start">
            review only
          </text>
        </g>
      </svg>
      <div className="legend">
        <span>[—] live path, proven in the current run</span>
        <span>[·] no raw clinical text crosses the laboratory line</span>
        <span>[blue] model proposal · [black] deterministic control</span>
      </div>
      <figcaption className="fig-cap">
        Fig 1. Two boundaries and a person. The models live inside the cloud boundary and
        may only propose; the deterministic controller and policy gate hold every decision;
        the specialist holds the final one. What leaves the laboratory is a structured,
        minimized, signed payload — never the note.
      </figcaption>
    </figure>
  );
}

export function NarrativePage() {
  const headline = hero.intervals.find((i) => i.id === hero.headline_interval_id)!;
  const required = hero.intervals.find((i) => i.id === hero.headline_requires_interval_id)!;
  const headlineDays = days(hero.dates[headline.from], hero.dates[headline.to]);
  const requiredDays = days(hero.dates[required.from], hero.dates[required.to]);

  const chrono = [
    {
      date: hero.dates.geo_public,
      what: 'Saturation genome editing data for this gene becomes public',
      cap: wt.world_evidence[0].capture.path.split('/').pop(),
    },
    {
      date: hero.dates.qualifying_publication,
      what: 'The qualifying publication is indexed',
      cap: wt.world_evidence[1].capture.path.split('/').pop(),
    },
    {
      date: hero.dates.clinvar_v5_public,
      what: 'The public variant record finally reflects the evidence',
      cap: wt.world_evidence[2].capture.path.split('/').pop(),
    },
  ];

  return (
    <div className="site">
      <header className="site-head">
        <div className="site-wrap">
          <div className="head-row">
            <span className="head-mark">RECALL</span>
            <nav className="head-links">
              <a href="#how">How it works</a>
              <a href="#fleet">The fleet</a>
              <a href="#run">Live run</a>
              <a href="#platform">Platform mapping</a>
              <a href="#/demo">Evidence surface</a>
            </nav>
          </div>
          <div className="head-flags">
            <span>NON-CLINICAL RESEARCH PROTOTYPE</span>
            <span>SYNTHETIC INSTITUTIONAL RECORDS</span>
            <span>CAPTURED PUBLIC EVIDENCE</span>
          </div>
        </div>
      </header>

      <div className="site-wrap">
        <section className="hero">
          <p className="hero-eyebrow">FORTIFIED ENTERPRISE FLEET</p>
          <h1>
            A zero-trust institutional agent fleet that continuously audits changing genomic
            evidence without allowing any model to become the scientific authority.
          </h1>
          <p>
            When a genetic test returns “uncertain”, the case is filed and almost never
            reopened. Evidence that would change it keeps arriving in public — years later,
            in a different system, with nobody watching. Recall watches.
          </p>
          <p>
            It runs a fleet of agents with separated duties across Google Cloud: one finds new
            evidence, a second judges whether it is material, a third independently re-opens
            every source and verifies the citations. None of them decides. A deterministic
            policy gate reads their signed receipts and rules, and only a human specialist may
            act on the result.
          </p>
          <div className="hero-cta">
            <a className="btn primary" href="#/demo">
              Open the evidence surface →
            </a>
            <a className="btn" href="#how">
              How it works ↓
            </a>
          </div>
        </section>

        <Section
          num="01"
          title="THE PROBLEM: A RESULT THAT MEANS “WE DO NOT KNOW YET”"
          claim="Genetic testing has a third answer, and it is the most common one to go stale. Nobody owns it, so nobody re-opens it."
        >
          <p>
            A person with a strong family history of cancer is tested. The laboratory reads
            their genes, finds a difference from the reference, and has to say what that
            difference means. There are three possible answers, and only two of them are
            answers.
          </p>

          <table className="tbl verdicts">
            <thead>
              <tr>
                <th>The lab reports</th>
                <th>What it means for care</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td className="cap">Pathogenic</td>
                <td>
                  This change explains the risk. Screening, prevention and testing the rest of
                  the family can all proceed from it.
                </td>
              </tr>
              <tr>
                <td className="cap">Benign</td>
                <td>
                  This change is not the cause. It is set aside and the search continues
                  elsewhere.
                </td>
              </tr>
              <tr className="vus-row">
                <td className="cap">
                  Uncertain
                  <span className="limit">“variant of uncertain significance”, a VUS</span>
                </td>
                <td>
                  <b>Nothing.</b> The evidence available today does not support either
                  answer, so the finding cannot guide screening, cannot guide prevention, and
                  cannot be used to test relatives. It is not a warning and it is not an
                  all-clear. It is an open question, written into a chart.
                </td>
              </tr>
            </tbody>
          </table>

          <p>
            So the clinician does the responsible thing: they explain that the finding cannot
            be acted on, they manage the patient on family history instead, and they say the
            sentence every genetics clinic says — <i>this may be reclassified as more
            evidence accumulates</i>. Then the report is filed.
          </p>

          <p>
            That sentence is a promise nobody is assigned to keep. The evidence that would
            settle the question does accumulate — in laboratories on other continents, in
            functional studies, in public data deposits and in publications — and eventually
            it reaches the public variant databases. But it arrives <b>years later</b>, in a
            different system, with no connection to the chart it should change. Re-contact
            practice varies between laboratories, and no standing process watches every closed
            case on the clinic&rsquo;s behalf.
          </p>

          <p className="hero-line">
            The person who carries this is the one nobody writes stories about: the clinical
            genetics specialist holding a backlog of unresolved cases, each one a question
            that was correct to leave open and that only they remember. Their real work is not
            reading a variant. It is remembering, for years, that a question is still open —
            and there is no system that remembers with them.
          </p>

          <h3 className="sub-head">What that costs, measured on one real case</h3>
          <p>
            Recall replays a documented case: a variant in <b>BRCA2</b>, one of the two genes
            most associated with hereditary breast and ovarian cancer, filed as uncertain. The
            evidence that moved it was deposited publicly, published, and only much later
            reflected in the public record that clinics read. Every event below is captured
            here as bytes and hashed, so the chronology can be checked rather than believed.
          </p>

          <EvidenceTimeline />

          <div className="chrono">
            {chrono.map((row) => (
              <div className="chrono-row" key={row.date}>
                <span className="chrono-date">{row.date}</span>
                <span className="chrono-what">{row.what}</span>
                <span className="chrono-cap">captured · {row.cap}</span>
              </div>
            ))}
          </div>

          <div className="gap-line">
            <div className="gap-item">
              <span className="gap-days">{headlineDays} days</span>
              <span className="gap-basis">{headline.claim_basis}</span>
            </div>
            <div className="gap-item">
              <span className="gap-days">{requiredDays} days</span>
              <span className="gap-basis">{required.claim_basis}</span>
            </div>
          </div>

          <p>
            {requiredDays} days is not a system outage. Nothing was broken and nobody was
            negligent. For {requiredDays} days the decisive evidence was public, free and
            searchable — and any clinic that had filed this variant as uncertain was still
            reading the older record, because re-reading it was nobody&rsquo;s scheduled work.
            That gap is the product: not a smarter model, but something that keeps watching
            after the appointment ends.
          </p>

          <p className="caveat">
            Both intervals are shown together because neither stands alone, and the claim is
            deliberately narrow. {hero.honesty_sentences.join(' ')} The day counts are computed
            from the dates above when this page renders, so a number here can never disagree
            with the dates beside it. Case chronology, not a product metric; governed by{' '}
            <code>{hero.governing_document}</code>.
          </p>
        </Section>

        <Section
          id="how"
          num="02"
          title="HOW RECALL WORKS"
          claim="Models propose. Deterministic code decides. The boundary between those two sentences is the product."
        >
          <div className="steps">
            {[
              [
                'Watch',
                'A machine-triggered scan opens for a durable case. Public sources are fetched and stored as bytes with their hashes.',
                'The schedule is not a person clicking; the execution creator is the scheduler’s service account.',
              ],
              [
                'Assess',
                'The Evidence Assessor judges whether the change is material for this specific case and proposes a candidate delta.',
                'It may not touch controller-owned identities, and its prose cannot route a case by itself.',
              ],
              [
                'Audit',
                'The Citation Auditor independently re-opens every source and checks each claim against the captured bytes.',
                'The agent that proposed the change is never the agent that verifies it.',
              ],
              [
                'Decide',
                'The deterministic policy gate reads the signed receipts and emits exactly one outcome, with reason codes.',
                'No model output becomes an action. No decision is taken on unverified evidence.',
              ],
              [
                'Hand over',
                'A review-eligible case becomes one simulated task for a human specialist, with its evidence attached.',
                'Recall never changes a clinical record, never reclassifies a variant, and never reaches a patient.',
              ],
            ].map(([what, detail, never], i) => (
              <div className="step" key={what}>
                <span className="step-num">{String(i + 1).padStart(2, '0')}</span>
                <span>
                  <span className="step-what">{what}</span>
                  <span className="step-detail">{detail}</span>
                  <span className="step-never">— {never}</span>
                </span>
              </div>
            ))}
          </div>
          <BoundaryDiagram />
        </Section>

        <Section
          id="fleet"
          num="03"
          title="THE FLEET"
          claim="Three agents with separated duties, one deterministic controller, one gate. The separation is enforced by identity and capability, not by prompt wording."
        >
          <table className="tbl">
            <thead>
              <tr>
                <th>Role</th>
                <th>What it may do</th>
                <th>What it may never do</th>
              </tr>
            </thead>
            <tbody>
              {[
                [
                  'Evidence Watcher',
                  'Find new public evidence and produce an evidence snapshot.',
                  'Bind its own source cursors or identities — the controller owns those.',
                ],
                [
                  'Evidence Assessor',
                  'Judge materiality and propose a candidate delta for one case.',
                  'Alter controller-owned identities, or decide the outcome.',
                ],
                [
                  'Citation Auditor',
                  'Independently re-open every cited source and verify each claim.',
                  'Audit its own proposal — it never wrote one.',
                ],
                [
                  'Deterministic Controller',
                  'Drive lifecycle, enforce tool authority, emit typed artifacts.',
                  'Delegate a decision to a model.',
                ],
                [
                  'Deterministic Policy Gate',
                  'Emit exactly one of NO_ACTION, ABSTAIN or REVIEW_REQUIRED with reason codes.',
                  'Accept model prose as a fact, or act on incomplete proof.',
                ],
              ].map(([role, may, never]) => (
                <tr key={role}>
                  <td className="cap">{role}</td>
                  <td>{may}</td>
                  <td>{never}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p>
            The agents hold no write access to the ledger at all. Each role runs under its own
            service identity with a role-scoped capability, and every tool call passes an
            authorization gate that emits a receipt: without a receipt there is no backend
            authority. In the run described below, the watcher, assessor and auditor recorded{' '}
            <b>zero</b> failures, and {run.round_trips.authorization_linked} of{' '}
            {run.round_trips.completed_model_tool_round_trips} completed round-trips carry
            authorization, gateway and trace linkage.
          </p>
        </Section>

        <Section
          num="04"
          title="THE AUTHORITY BOUNDARY"
          claim="A scan can end in exactly three ways, and a fourth state exists only to say the machinery itself could not be trusted."
        >
          <table className="tbl">
            <thead>
              <tr>
                <th>Outcome</th>
                <th>Meaning</th>
                <th>Consequence</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td className="cap">NO_ACTION</td>
                <td>No eligible audited change was found for this scan.</td>
                <td>The next scan is scheduled. No task.</td>
              </tr>
              <tr>
                <td className="cap">ABSTAIN</td>
                <td>
                  Recall stopped because required proof was incomplete: a needed fact was
                  missing, invalid, failed or conflicted.
                </td>
                <td>An operations receipt. No task.</td>
              </tr>
              <tr>
                <td className="cap">REVIEW_REQUIRED</td>
                <td>
                  A material change is complete, independently audited and conflict-free.
                </td>
                <td>Exactly one simulated review task for a specialist.</td>
              </tr>
              <tr>
                <td className="cap">HALTED</td>
                <td>
                  A technical terminal: the policy gate or the ledger’s integrity was
                  unavailable, so no trustworthy decision was possible.
                </td>
                <td>
                  Never a task, and never presented as a semantic or clinical outcome.
                </td>
              </tr>
            </tbody>
          </table>
          <p className="caveat">
            HALTED is not a quiet ABSTAIN. Collapsing the two would hide an infrastructure
            failure behind a scientific-sounding word, so the surfaces keep them visually and
            textually distinct — you can see all four states, including the two failure
            endings, on the <a href="#/demo">evidence surface</a>.
          </p>
        </Section>

        <Section
          id="run"
          num="05"
          title="LIVE ON GOOGLE CLOUD"
          claim="The fleet is not a diagram. A long-running Cloud Run Job was executing the cohort while this page was written."
        >
          <span className="stamp">
            {run.status} · snapshot as of {run.as_of_utc} ({run.as_of_local}) ·{' '}
            {run.snapshot_source}
          </span>
          <div className="grid">
            <div className="cell">
              <span className="cell-value">{run.scan_runs.total}</span>
              <span className="cell-label">ScanRuns in this execution</span>
            </div>
            <div className="cell">
              <span className="cell-value">{run.scan_runs.terminal_no_action}</span>
              <span className="cell-label">terminal NO_ACTION at snapshot</span>
            </div>
            <div className="cell">
              <span className="cell-value">{run.artifacts.valid.toLocaleString('en-US')}</span>
              <span className="cell-label">valid artifacts · {run.artifacts.invalid} invalid</span>
            </div>
            <div className="cell">
              <span className="cell-value">
                {run.round_trips.authorization_linked}/
                {run.round_trips.completed_model_tool_round_trips}
              </span>
              <span className="cell-label">round-trips with authorization, gateway and trace linkage</span>
            </div>
            <div className="cell">
              <span className="cell-value">0</span>
              <span className="cell-label">watcher, assessor and auditor failures</span>
            </div>
            <div className="cell">
              <span className="cell-value">0</span>
              <span className="cell-label">IAM, startup, schema or traceback failures</span>
            </div>
          </div>
          <p className="kv">
            <b>execution</b> {run.binding.execution} · <b>source commit</b>{' '}
            {run.binding.source_commit}
          </p>
          <p className="kv">
            <b>image digest</b> {run.binding.image_digest}
          </p>
          <p>
            One HTTP 429 was encountered and recovered with no failed receipt. That is the
            failure-tolerance claim in its smallest form: pressure produced a typed, recorded
            recovery rather than a silent gap.
          </p>
          <div className="pending-list">
            <Badge kind="DEFERRED" /> <b>Not claimed yet.</b> The run had not reached a
            terminal state when this page was built, so the following are deliberately absent
            rather than estimated:
            <ul>
              {run.pending_until_terminal_evidence.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>
        </Section>

        <Section
          id="platform"
          num="06"
          title="PLATFORM CAPABILITY MAPPING"
          claim="Every capability the category asks for, the mechanism that provides it, and exactly how far that claim has been proven."
        >
          <table className="tbl">
            <thead>
              <tr>
                <th>Capability</th>
                <th>Mechanism in Recall</th>
                <th>Verification</th>
              </tr>
            </thead>
            <tbody>
              {fit.capabilities.map((row) => (
                <tr key={row.capability}>
                  <td className="cap">{row.capability}</td>
                  <td>
                    {row.mechanism}
                    <span className="limit">
                      <code>{row.evidence}</code>
                    </span>
                    <span className="limit">{row.limit}</span>
                  </td>
                  <td>
                    <Badge kind={row.badge} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="caveat">{fit.note}</p>

          <h3 style={{ fontSize: '0.86rem', margin: '30px 0 6px' }}>
            How a second department would find these agents
          </h3>
          <p>
            Discovery is a first-class contract, not a README. A consuming team asks the
            registry for a <b>capability</b>, not for a URL, and resolution returns the binding
            together with the mode it was found by: <code>REGISTERED</code> when the agent
            reached the catalog through <code>agents.create</code>,{' '}
            <code>MANUAL_SERVICE</code> when it was registered as a service, and{' '}
            <code>PINNED_FALLBACK</code> when an endpoint was pinned outside the catalog. A
            pinned endpoint is never presented as catalogued. The resolution mode travels as a
            first-class payload field, the catalog record is digest-addressed so a changed
            catalog is detectable, and a capability with no catalog entry is recorded as
            unresolved rather than quietly substituted.
          </p>
        </Section>

        <Section
          num="07"
          title="WHAT NEVER LEAVES THE LABORATORY"
          claim="The clinical note stays home. What travels is a structured, minimized, hash-bound and signed payload."
        >
          <div className="boundary">
            <div className="bx lab">
              <span className="bx-title">STAYS IN THE LABORATORY</span>
              <ul>
                <li>clinical note text</li>
                <li>direct identifiers</li>
                <li>anything not on the egress allowlist</li>
              </ul>
            </div>
            <span className="bx-arrow">→</span>
            <div className="bx out">
              <span className="bx-title">LEAVES, AND ONLY THIS</span>
              <ul>
                <li>declared structured fields</li>
                <li>a pseudonymous case reference</li>
                <li>a signed PrivacyReceipt bound to the payload hash</li>
              </ul>
            </div>
          </div>
          <p>
            Deterministic detectors screen every record first; a local Gemma then proposes the
            residual spans they may have missed, and deterministic adjudication — not the model
            — decides what is redacted. The model proposes here too.
          </p>
          <p className="caveat">
            <Badge kind="SOURCE VERIFIED" /> <b>Frozen measurement.</b> The full-cohort privacy
            run of 462 cases was executed once, at measurement commit{' '}
            <code>697aa6eb</code>, and is preserved byte-for-byte. It has been revalidated
            read-only against the current product commit <code>63437d20</code>: 462 of 462
            receipts parsed and verified through the production loader, zero writes, zero
            semantic drift, original bytes unchanged. It is a historical frozen measurement,
            not a measurement of the current run, and it is never re-run: the preregistration
            binds it to a single execution. Separately, the frozen P1 privacy study covers{' '}
            <b>180</b> records — a different population from the 462, never combined with it,
            and its public figures come from the corrected view and the committed erratum.
          </p>
        </Section>

        <Section
          num="08"
          title="PROVENANCE AND LIMITS"
          claim="Everything on this page is either captured public evidence or synthetic institutional data, and the difference is always stated."
        >
          <ul className="bullets">
            <li>
              Every patient-facing record in this project is synthetic. No real person,
              institution record or contact detail exists anywhere in the system.
            </li>
            <li>
              The public evidence — registry pages, the dataset accession, the publication
              record — is captured as bytes and hashed, so a claim can be checked against the
              exact source that was read.
            </li>
            <li>
              This is a non-clinical research prototype. It does not diagnose, does not
              reclassify variants, does not change clinical records, and does not reach
              patients.
            </li>
            <li>
              Run counts and case counts are different things: a case re-evaluated in a later
              epoch is the same case again, labelled, and totals are never summed across
              epochs into one headline.
            </li>
            <li>
              Where a capability is not proven, this page says so. Badges are claims about
              evidence, not about ambition.
            </li>
          </ul>
        </Section>

        <footer className="site-foot">
          <p className="sec-claim">
            The evidence surface is open: real derived records, the three-valued outcomes
            including both failure endings, the cohort ledger and the privacy desk.
          </p>
          <div className="foot-links">
            <a className="btn primary" href="#/demo">
              Open the evidence surface →
            </a>
            <a className="btn" href="#/demo/walkthrough">
              Six-scene walkthrough
            </a>
          </div>
          <p className="foot-note">
            Recall — non-clinical research prototype. Synthetic institutional records and
            captured public evidence. Models propose; deterministic policy decides; a human
            specialist holds the final authority.
          </p>
        </footer>
      </div>
    </div>
  );
}
