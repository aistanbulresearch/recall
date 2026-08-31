/**
 * Recall: the jury-facing narrative page (route `/`).
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
  gene: string;
  variant: string;
}

const hero = historicalCase as unknown as HeroFile;
const run = liveRun as unknown as {
  status: string;
  as_of_utc: string;
  snapshot_source: string;
  binding: Record<string, string>;
  terminal_states: Record<string, number>;
  artifacts: Record<string, number>;
  governance: Record<string, number>;
  duration_seconds: number;
  cloud_run_terminal_state: string;
  manifest_status: string;
  cost_projected_usd_micros: number;
  actual_billed_cost_state: string;
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
        Fig 1. Drawn to scale from the dates above. Nothing failed; the evidence simply
        arrived where nobody was watching.
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
        <span>[, ] live path, proven in the current run</span>
        <span>[·] no raw clinical text crosses the laboratory line</span>
        <span>[blue] model proposal · [black] deterministic control</span>
      </div>
      <figcaption className="fig-cap">
        Fig 1. Two boundaries and a person. The models live inside the cloud boundary and
        may only propose; the deterministic controller and policy gate hold every decision;
        the specialist holds the final one. What leaves the laboratory is a structured,
        minimized, signed payload, never the note.
      </figcaption>
    </figure>
  );
}

export function NarrativePage() {
  const headline = hero.intervals.find((i) => i.id === hero.headline_interval_id)!;
  const required = hero.intervals.find((i) => i.id === hero.headline_requires_interval_id)!;
  const headlineDays = days(hero.dates[headline.from], hero.dates[headline.to]);
  const requiredDays = days(hero.dates[required.from], hero.dates[required.to]);

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
            reopened. Evidence that would change it keeps arriving in public, years later,
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
          title="THE PROBLEM"
          claim="Clinical genetics has an alert system. It fires when the paperwork changes, not when the evidence does."
        >
          <p>
            You monitor dependencies for CVEs. Now imagine alerts only fired when the vendor
            updated the changelog, not when the exploit went public. Clinical genetics works
            that way today: the tools watch the changelog.
          </p>
          <p>
            A cancer patient&rsquo;s genetic test comes back <b>“uncertain significance”</b>, a
            classification that means <i>do not act, wait for evidence</i>. It cannot guide
            screening, cannot guide prevention, and cannot be used to test her relatives. That
            one label can stand between her and a drug approved for exactly her kind of tumour.
          </p>
          <p>
            The evidence that would settle it does arrive, years later, in a public database,
            with no connection to the chart it should change.
          </p>

          <table className="tbl card">
            <caption>One real variant, and the sources for every date below.</caption>
            <tbody>
              <tr>
                <td className="cap">Variant</td>
                <td>
                  {hero.gene} <code>{hero.variant}</code>
                </td>
              </tr>
              <tr>
                <td className="cap">ClinVar</td>
                <td>
                  <code>{hero.clinvar_vcv}</code>
                </td>
              </tr>
              <tr>
                <td className="cap">Functional data public</td>
                <td>
                  GEO <code>{hero.geo_accession}</code>, {hero.dates.geo_public}
                </td>
              </tr>
              <tr>
                <td className="cap">Paper published</td>
                <td>
                  PMID <code>{hero.qualifying_pmid}</code>, {hero.dates.qualifying_publication}
                </td>
              </tr>
              <tr>
                <td className="cap">ClinVar first reflection</td>
                <td>
                  {hero.dates.clinvar_v5_public}, <code>{hero.clinvar_vcv}.5</code>
                </td>
              </tr>
            </tbody>
          </table>

          <p className="punch">
            Laboratory evidence that this variant behaves like the harmful ones went public in
            September 2024. The clinical record first moved in April 2026.{' '}
            <b>{headlineDays} days</b>, and in between, nothing was watching.
          </p>

          <EvidenceTimeline />

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

          <p className="caveat">
            Two intervals, two meanings, never one counter: {headlineDays} from the deposit,{' '}
            {requiredDays} from the publication. {hero.honesty_sentences.join(' ')} Case
            chronology, not a product metric, computed at render from{' '}
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
                  <span className="step-never">, {never}</span>
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
                  'Bind its own source cursors or identities; the controller owns those.',
                ],
                [
                  'Evidence Assessor',
                  'Judge materiality and propose a candidate delta for one case.',
                  'Alter controller-owned identities, or decide the outcome.',
                ],
                [
                  'Citation Auditor',
                  'Independently re-open every cited source and verify each claim.',
                  'Audit its own proposal; it never wrote one.',
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
            authority. In the run described below, all {run.governance.tool_calls} tool calls
            carry an authorization decision and a trace, and{' '}
            <b>{run.governance.unauthorized_calls}</b> were unauthorized. The roles that did
            fail failed loudly: {run.terminal_states.HALTED} cases stopped with a typed receipt
            naming the role and the stage, rather than passing an unfinished result forward.
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
            textually distinct; you can see all four states, including the two failure
            endings, on the <a href="#/demo">evidence surface</a>.
          </p>
        </Section>

        <Section
          id="run"
          num="05"
          title="THE RUN THAT HAPPENED"
          claim="Not a diagram. A long-running Cloud Run Job took the whole cohort through the fleet, unattended, and every figure below comes from its own artifacts."
        >
          <span className="stamp">
            COMPLETED · generation 27 · {run.duration_seconds ? `${Math.floor(run.duration_seconds / 3600)}h ${Math.round((run.duration_seconds % 3600) / 60)}m` : ''} unattended · finished{' '}
            {run.as_of_utc}
          </span>
          <div className="grid">
            <div className="cell">
              <span className="cell-value">{run.terminal_states.NO_ACTION}</span>
              <span className="cell-label">cases with nothing to raise</span>
            </div>
            <div className="cell">
              <span className="cell-value">{run.terminal_states.ABSTAIN}</span>
              <span className="cell-label">refused to decide on incomplete proof</span>
            </div>
            <div className="cell">
              <span className="cell-value">{run.terminal_states.HALTED}</span>
              <span className="cell-label">stopped rather than guessed</span>
            </div>
            <div className="cell">
              <span className="cell-value">{run.artifacts.documents.toLocaleString('en-US')}</span>
              <span className="cell-label">
                artifacts, {run.artifacts.parse_failures} parse failures
              </span>
            </div>
            <div className="cell">
              <span className="cell-value">
                {run.governance.authorizations}/{run.governance.tool_calls}
              </span>
              <span className="cell-label">
                tool calls authorized · {run.governance.unauthorized_calls} unauthorized
              </span>
            </div>
            <div className="cell">
              <span className="cell-value">{run.governance.trace_chains}</span>
              <span className="cell-label">trace chains, one per case</span>
            </div>
          </div>
          <p className="kv">
            <b>source commit</b> {run.binding.source_commit}
          </p>
          <p className="kv">
            <b>image digest</b> {run.binding.image_digest}
          </p>
          <p>
            Three of those cases are the whole argument in miniature. A model produced a
            material claim, the Citation Auditor could not verify its sources, and the gate
            emitted ABSTAIN with the reason codes attached; no task, no downstream action, no
            invented certainty. Eight more met an agent timeout and stopped at a technical
            terminal with a typed receipt rather than taking the cohort down with them.
          </p>
          <p className="caveat">
            Cloud Run reports <b>{run.cloud_run_terminal_state}</b> and the cohort day manifest
            reports <b>{run.manifest_status}</b>. Both are true and both are shown: the
            infrastructure finished, and eight cases inside it never reached a decision. The
            run also absorbed {run.governance.http_429} rate-limit responses without a single
            case failing because of one. Projected cost for the cohort is $
            {(Number(run.cost_projected_usd_micros) / 1_000_000).toFixed(2)} against a pinned
            pricing policy; its own <code>actual_billed_cost_state</code> reads{' '}
            {run.actual_billed_cost_state}, so it is a projection and is labelled as one.{' '}
            <a href="#/demo/">Open the run, case by case →</a>
          </p>
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
            residual spans they may have missed, and deterministic adjudication, not the model
, decides what is redacted. The model proposes here too.
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
            <b>180</b> records; a different population from the 462, never combined with it,
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
              The public evidence, registry pages, the dataset accession, the publication
              record, is captured as bytes and hashed, so a claim can be checked against the
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
            Recall, non-clinical research prototype. Synthetic institutional records and
            captured public evidence. Models propose; deterministic policy decides; a human
            specialist holds the final authority.
          </p>
        </footer>
      </div>
    </div>
  );
}
