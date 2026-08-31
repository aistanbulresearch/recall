/**
 * The walkthrough: one synthetic patient, one real variant chronology, six
 * scenes. Each scene shows WHAT THE CLINICIAN SEES (a realistic laboratory /
 * EHR surface — synthetic, and labelled so) and, beside it, WHAT RUNS BEHIND
 * that screen (the fleet, the gate, the privacy boundary) with the real
 * evidence chips.
 *
 * Honesty frame: the patient is fabricated and the file that defines her says
 * so; the variant's registry chronology is real captured history; every hash
 * chip resolves from a committed file through the evidence-file registry.
 */

import type { ReactNode } from 'react';

import { buildViewModel } from '../../viewmodel/builder';
import goldenBundle from '../../bundles/golden.json';
import type { ArtifactBundle } from '../../viewmodel/types';
import {
  GEMMA_RUN_FIELDS,
  HERO_CASE_FIELDS,
  P1_FIELDS,
  WALKTHROUGH_FIELDS,
  historicalCase,
  walkthroughCase,
} from '../evidence-files';
import { DerivedValue, fieldToStripEntry, useStripEntries } from '../strip';
import { recordStamp } from './Worklist';

const golden = buildViewModel(goldenBundle as unknown as ArtifactBundle);

interface WtFile {
  patient: {
    name: string;
    mrn: string;
    born: string;
    sex: string;
    clinic: string;
    first_visit: string;
    referral_reason: string;
  };
  encounter: { date: string; panel: string; note_excerpt: string };
  world_evidence: { id: string; what: string; capture: { path: string } }[];
}

const wt = walkthroughCase as unknown as WtFile;

interface HeroFile {
  dates: Record<string, string>;
  intervals: { id: string; from: string; to: string; claim_basis: string }[];
  headline_interval_id: string;
  headline_requires_interval_id: string;
}

const heroFile = historicalCase as unknown as HeroFile;

function daysBetween(fromIso: string, toIso: string): number {
  return Math.round(
    (Date.parse(`${toIso}T00:00:00Z`) - Date.parse(`${fromIso}T00:00:00Z`)) / 86_400_000,
  );
}

function W(key: string) {
  return <DerivedValue entry={WALKTHROUGH_FIELDS[key]} />;
}

function Scene({
  index,
  title,
  kicker,
  screen,
  behind,
}: {
  index: number;
  title: string;
  kicker: string;
  screen: ReactNode;
  behind: ReactNode;
}) {
  return (
    <section className="scene">
      <header className="scene-head">
        <span className="scene-index">{String(index).padStart(2, '0')}</span>
        <div>
          <h2>{title}</h2>
          <p className="scene-kicker">{kicker}</p>
        </div>
      </header>
      <div className="scene-body">
        <div className="scene-screen">
          <div className="screen-tag">WHAT THE CLINICIAN SEES</div>
          {screen}
        </div>
        <div className="scene-behind">
          <div className="behind-tag">WHAT RUNS BEHIND THIS SCREEN</div>
          {behind}
        </div>
      </div>
    </section>
  );
}

function PatientBanner() {
  return (
    <div className="ehr-banner">
      <div className="ehr-avatar" aria-hidden>
        {String(WALKTHROUGH_FIELDS['EV-WT-PATIENT'].value).slice(0, 1)}
      </div>
      <div className="ehr-id">
        <span className="ehr-name">
          {W('EV-WT-PATIENT')} <span className="syn-tag">SYNTHETIC PATIENT</span>
        </span>
        <span className="ehr-meta">
          MRN {W('EV-WT-MRN')} · born {W('EV-WT-BORN')} · {wt.patient.sex} · {wt.patient.clinic}
        </span>
      </div>
      <div className="ehr-visit">
        <span>first visit</span>
        {W('EV-WT-FIRST-VISIT')}
      </div>
    </div>
  );
}

export function Walkthrough() {
  useStripEntries('walkthrough', [
    ...Object.values(WALKTHROUGH_FIELDS),
    HERO_CASE_FIELDS['EV-HERO-DATE-DATA'],
    HERO_CASE_FIELDS['EV-HERO-DATE-PAPER'],
    HERO_CASE_FIELDS['EV-HERO-DATE-CLINVAR'],
    fieldToStripEntry(golden.fields['UI-POLICY-OUTCOME']),
    fieldToStripEntry(golden.fields['UI-PRIVACY-RAW-TEXT-EGRESS']),
    GEMMA_RUN_FIELDS['EV-GEMMA-RECEIPTS'],
    P1_FIELDS['EV-P1-ARM-B-ACCEPTED'],
  ]);

  const headline = heroFile.intervals.find((i) => i.id === heroFile.headline_interval_id)!;
  const required = heroFile.intervals.find(
    (i) => i.id === heroFile.headline_requires_interval_id,
  )!;
  const headlineDays = daysBetween(heroFile.dates[headline.from], heroFile.dates[headline.to]);
  const requiredDays = daysBetween(heroFile.dates[required.from], heroFile.dates[required.to]);
  const stamp = recordStamp(golden.fields);
  const reasons = golden.fields['UI-POLICY-REASONS'].items.map(String);

  return (
    <div className="walkthrough">
      <header className="wt-hero">
        <p className="wt-eyebrow">A WALKTHROUGH IN SIX SCENES</p>
        <h1>The result was filed as “uncertain”. The world kept moving.</h1>
        <p className="wt-lede">
          One synthetic patient, one real variant history. What a clinician sees at every step —
          and the fleet, gate and privacy boundary running underneath it.
        </p>
      </header>

      <Scene
        index={1}
        title="The clinic files a VUS"
        kicker="The problem is not a wrong answer — it is an answer nobody will revisit."
        screen={
          <div className="ehr">
            <PatientBanner />
            <div className="ehr-tabs" aria-hidden>
              <span className="ehr-tab active">Genomic report</span>
              <span className="ehr-tab">Encounters</span>
              <span className="ehr-tab">Documents</span>
            </div>
            <table className="ehr-result">
              <thead>
                <tr>
                  <th>Gene</th>
                  <th>Variant</th>
                  <th>Interpretation</th>
                  <th>Reported</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>{W('EV-WT-RESULT-GENE')}</td>
                  <td>{W('EV-WT-RESULT-VARIANT')}</td>
                  <td>
                    <span className="vus-chip">{W('EV-WT-RESULT-THEN')}</span>
                  </td>
                  <td>{W('EV-WT-ENCOUNTER-DATE')}</td>
                </tr>
              </tbody>
            </table>
            <div className="ehr-note">
              <span className="ehr-note-head">Encounter note — {wt.encounter.panel}</span>
              <p>{wt.encounter.note_excerpt}</p>
            </div>
          </div>
        }
        behind={
          <>
            <p>
              Nothing runs. That is the point: the interpretation was honest for its date
              ({W('EV-WT-RESULT-BASIS')}) — and once filed, no clinic re-reviews it on its own.
            </p>
            <p className="behind-evidence">
              The record state at that date is captured, byte for byte:{' '}
              <code>{wt.encounter && 'artifacts/evidence/rcl-205/clinvar/…v4…'}</code> sha256{' '}
              {W('EV-WT-V4-CAPTURE')}
            </p>
          </>
        }
      />

      <Scene
        index={2}
        title="The world moves"
        kicker="Decisive evidence appears in public — but not in the chart."
        screen={
          <div className="world-feed">
            {wt.world_evidence.map((row, i) => (
              <div className="world-row" key={row.id}>
                <span className="world-date">
                  <DerivedValue
                    entry={
                      [
                        HERO_CASE_FIELDS['EV-HERO-DATE-DATA'],
                        HERO_CASE_FIELDS['EV-HERO-DATE-PAPER'],
                        HERO_CASE_FIELDS['EV-HERO-DATE-CLINVAR'],
                      ][i]
                    }
                  />
                </span>
                <span className="world-what">{row.what}</span>
                <span className="world-capture">
                  captured · <code>{row.capture.path.split('/').slice(-1)[0]}</code>
                </span>
              </div>
            ))}
          </div>
        }
        behind={
          <>
            <p>
              Recall's <strong>Watcher</strong> scans these sources on a machine-triggered
              schedule — a Cloud Scheduler cron starts a Cloud Run job; the execution's creator
              is the scheduler's service account, not a person. Source pages are captured as
              bytes and hashed.
            </p>
            <p className="behind-evidence">
              capture hashes: GEO {W('EV-WT-GEO-CAPTURE')} · results {W('EV-WT-SGE-CAPTURE')} ·
              paper {W('EV-WT-PAPER-CAPTURE')} · ClinVar v5 {W('EV-WT-V5-CAPTURE')}
            </p>
          </>
        }
      />

      <Scene
        index={3}
        title="The fleet works the case"
        kicker="Three roles, separated on purpose. The clinician sees none of this — yet."
        screen={
          <div className="trace">
            {[
              ['Watcher', 'saw the new evidence and opened a re-evaluation', 'evidence.watch'],
              ['Assessor', 'judged it material for this variant', 'materiality.assess'],
              ['Auditor', 'verified every citation against the captured bytes', 'citation.audit'],
            ].map(([role, what, capability], i) => (
              <div className="trace-span" key={role} style={{ marginLeft: `${i * 26}px` }}>
                <span className="trace-role">{role}</span>
                <span className="trace-what">{what}</span>
                <code className="trace-cap">{capability}</code>
              </div>
            ))}
            <div className="trace-span gate" style={{ marginLeft: '78px' }}>
              <span className="trace-role">Policy Gate</span>
              <span className="trace-what">decides — deterministically</span>
            </div>
          </div>
        }
        behind={
          <>
            <p>
              Each role runs under its own service account with its own capability; the agent
              that proposes is never the agent that verifies. The Auditor's approval only counts
              when the quoted source resolves to the captured bytes from scene 2 — a mismatched
              quote is a refusal, not a warning.
            </p>
            <p className="behind-evidence">
              runtime: in-process ADK on Cloud Run · trace spans carry no prompt text · roster and
              validation status per case in the dossier
            </p>
          </>
        }
      />

      <Scene
        index={4}
        title="The gate decides"
        kicker="No agent decides. A deterministic gate reads the receipts and rules."
        screen={
          <div className={`gate-card tone-${stamp.tone}`}>
            <span className="gate-stamp">{stamp.label}</span>
            <span className="gate-code">
              outcome{' '}
              <DerivedValue entry={fieldToStripEntry(golden.fields['UI-POLICY-OUTCOME'])} />
            </span>
            <ul className="gate-reasons">
              {reasons.map((reason) => (
                <li key={reason}>
                  <code>{reason}</code>
                </li>
              ))}
            </ul>
          </div>
        }
        behind={
          <>
            <p>
              The gate is lexical and reason-coded: same receipts, same ruling, every time. And it
              is three-valued — when evidence does not verify it{' '}
              <a href="#/demo/case/fault">abstains</a>; when integrity cannot be proven it{' '}
              <a href="#/demo/case/halted">halts</a>. Both are honest endings, recorded like any other.
            </p>
            <p className="behind-evidence">
              this scene renders the audited replay bundle's derived fields — outcome and reason
              codes are read, never asserted
            </p>
          </>
        }
      />

      <Scene
        index={5}
        title="Back at the clinic"
        kicker="The case reopens itself — with the evidence attached."
        screen={
          <div className="ehr">
            <PatientBanner />
            <div className="worklist-pop">
              <span className={`stamp tone-${stamp.tone}`}>{stamp.label}</span>
              <span className="pop-line">
                {W('EV-WT-RESULT-GENE')} {W('EV-WT-RESULT-VARIANT')} — new evidence verified to
                source; specialist review suggested.
              </span>
            </div>
            <div className="interval-cards compact">
              <article className="interval-card headline">
                <span className="interval-days">{headlineDays} days</span>
                <span className="interval-basis">{headline.claim_basis}</span>
              </article>
              <article className="interval-card">
                <span className="interval-days">{requiredDays} days</span>
                <span className="interval-basis">{required.claim_basis}</span>
              </article>
            </div>
          </div>
        }
        behind={
          <>
            <p>
              That interval is what Recall exists to close: the historical gap between evidence
              being public and the record reflecting it, measured on this case's real registry
              chronology. Case chronology, not a product metric — and the fleet raises the case
              as soon as the evidence is captured and verified.
            </p>
            <p className="behind-evidence">
              day counts computed at render time from the governed case file · full chronology and
              honesty sentences: <a href="#/demo/case/hero">the hero case page</a>
            </p>
          </>
        }
      />

      <Scene
        index={6}
        title="What never left the lab"
        kicker="The note stayed home. The proof travelled."
        screen={
          <div className="privacy-visual">
            <div className="pv-box lab">
              <span className="pv-title">LABORATORY</span>
              <span className="pv-item">clinical note text</span>
              <span className="pv-item">identifiers</span>
              <span className="pv-lock" aria-hidden>⬤ stays</span>
            </div>
            <div className="pv-arrow" aria-hidden>→</div>
            <div className="pv-box cloud">
              <span className="pv-title">LEAVES THE LAB</span>
              <span className="pv-item">structured fields only</span>
              <span className="pv-item">
                raw-text egress{' '}
                <DerivedValue
                  entry={fieldToStripEntry(golden.fields['UI-PRIVACY-RAW-TEXT-EGRESS'])}
                />
              </span>
              <span className="pv-item">signed receipt (hash-bound)</span>
            </div>
          </div>
        }
        behind={
          <>
            <p>
              Before anything leaves, a deterministic screen runs — and a local Gemma checks what
              it might have missed: acceptance {P1_FIELDS && <DerivedValue entry={P1_FIELDS['EV-P1-BASELINE-ACCEPTED']} />}
              /180 → <DerivedValue entry={P1_FIELDS['EV-P1-ARM-B-ACCEPTED']} />/180 in the frozen
              study, with zero escaped identifiers. Last night the whole portfolio —{' '}
              <DerivedValue entry={GEMMA_RUN_FIELDS['EV-GEMMA-RECEIPTS']} /> cases — went through
              the live gate on a private Vertex endpoint.
            </p>
            <p className="behind-evidence">
              full figures, hashes and locus: <a href="#/demo/privacy">the privacy desk</a>
            </p>
          </>
        }
      />

      <footer className="wt-close">
        <h2>The evidence file is open</h2>
        <p>
          Everything above resolves from committed artifacts — the strip below shows the lineage
          of every figure on this page. Keep going:
        </p>
        <nav className="wt-links">
          <a href="#/demo/">Worklist</a>
          <a href="#/demo/cohort">Cohort ledger</a>
          <a href="#/demo/privacy">Privacy desk</a>
          <a href="#/demo/dossier">Evidence dossier</a>
        </nav>
      </footer>
    </div>
  );
}
