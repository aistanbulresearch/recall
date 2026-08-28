/**
 * Clinician worklist: what lands on a reviewer's desk.
 *
 * Each row is one completed fleet evaluation whose figures are derived from
 * that scenario's artifact bundle. The plain-language outcome label is a
 * deterministic mapping from the gate's derived outcome value — never free
 * text. Cohort rows that do not exist yet are explicit PENDING placeholders.
 */

import type { Scenario } from '../Workbench';
import type { ViewModel } from '../../viewmodel/types';
import { HERO_CASE_FIELDS } from '../evidence-files';
import { DerivedValue, fieldToStripEntry, useStripEntries } from '../strip';

interface BuildResult {
  fields: ViewModel;
}

/** Deterministic plain-language labels, keyed by the derived gate outcome. */
export const OUTCOME_LANGUAGE: Record<string, { label: string; tone: string }> = {
  REVIEW_REQUIRED: { label: 'Human review requested', tone: 'review' },
  ABSTAIN: { label: 'Fleet abstained — evidence did not verify', tone: 'abstain' },
  HALTED: { label: 'Run halted — integrity could not be proven', tone: 'halted' },
};

export function outcomeStamp(value: string | number | null) {
  const language = OUTCOME_LANGUAGE[String(value ?? '')];
  return language ?? { label: String(value ?? 'UNRESOLVED'), tone: 'unknown' };
}

/**
 * The stamp for a whole record, derived deterministically from two fields:
 * when the gate decided, its outcome speaks; when the run halted before the
 * gate could decide, the run state speaks and says exactly that.
 */
export function recordStamp(fields: ViewModel) {
  const outcome = fields['UI-POLICY-OUTCOME'];
  if (outcome.status === 'KNOWN' && outcome.value !== null) {
    return outcomeStamp(outcome.value);
  }
  if (fields['UI-GLOBAL-RUN-STATE'].value === 'HALTED') {
    return {
      label: 'Run halted — the gate never decided',
      tone: 'halted',
    };
  }
  return outcomeStamp(outcome.value);
}

const ROW_FIELDS = [
  'UI-POLICY-OUTCOME',
  'UI-GLOBAL-RUN-STATE',
  'UI-CITATION-STATUS',
  'UI-PRIVACY-STATUS',
  'UI-GLOBAL-RUN-ID',
] as const;

export function Worklist({
  scenarios,
  models,
}: {
  scenarios: readonly Scenario[];
  models: Record<string, BuildResult>;
}) {
  const stripEntries = scenarios.flatMap((scenario) =>
    ROW_FIELDS.map((id) => {
      const field = models[scenario.id].fields[id];
      return { ...fieldToStripEntry(field), key: `${scenario.id}:${id}` };
    }),
  ).concat([HERO_CASE_FIELDS['EV-HERO-VARIANT'], HERO_CASE_FIELDS['EV-HERO-VCV']]);
  useStripEntries('worklist', stripEntries);

  return (
    <section className="worklist">
      <header className="view-head">
        <h1>Re-evaluation worklist</h1>
        <p className="view-sub">
          Cases the fleet has re-evaluated against new evidence. Outcomes are decided by the
          deterministic policy gate; this desk only reads them.
        </p>
      </header>

      <div className="work-card hero-row">
        <a className="work-row" href="#/case/hero">
          <div className="work-case">
            <span className="work-title">
              {String(HERO_CASE_FIELDS['EV-HERO-GENE'].value)}{' '}
              <DerivedValue entry={HERO_CASE_FIELDS['EV-HERO-VARIANT']} />
            </span>
            <span className="work-meta">
              Historical replay case ·{' '}
              <DerivedValue entry={HERO_CASE_FIELDS['EV-HERO-VCV']} />
            </span>
          </div>
          <span className="stamp tone-review">EVIDENCE GAP MEASURED</span>
        </a>
      </div>

      <div className="work-card">
        {scenarios.map((scenario) => {
          const fields = models[scenario.id].fields;
          const stamp = recordStamp(fields);
          return (
            <a className="work-row" key={scenario.id} href={`#/case/${scenario.id}`}>
              <div className="work-case">
                <span className="work-title">{scenario.clinicalLabel}</span>
                <span className="work-meta">
                  run{' '}
                  <DerivedValue
                    entry={{
                      ...fieldToStripEntry(fields['UI-GLOBAL-RUN-ID']),
                      key: `${scenario.id}:UI-GLOBAL-RUN-ID`,
                    }}
                  />{' '}
                  · citations {String(fields['UI-CITATION-STATUS'].value ?? '—')} · privacy{' '}
                  {String(fields['UI-PRIVACY-STATUS'].value ?? '—')}
                </span>
              </div>
              <span className={`stamp tone-${stamp.tone}`}>{stamp.label}</span>
            </a>
          );
        })}
      </div>

      <div className="work-card pending-block" aria-label="Pending cohort results">
        <div className="pending-head">
          <span className="stamp tone-pending">PENDING</span>
          <span>
            Full-cohort re-scan rows (ramp r1/r2/r3 and the final single-cycle re-evaluation)
            fill from the morning bundle regeneration. No figure is shown before its manifest
            exists.
          </span>
        </div>
        {['Ramp r1', 'Ramp r2', 'Ramp r3', 'Final full-cohort cycle'].map((label) => (
          <div className="work-row pending" key={label}>
            <div className="work-case">
              <span className="work-title">{label}</span>
              <span className="work-meta">awaiting executed manifest</span>
            </div>
            <span className="stamp tone-pending">PENDING</span>
          </div>
        ))}
      </div>

      <p className="honesty-footnote">
        Run counts and case counts are different things: a case re-evaluated in several epochs
        appears once per epoch, labelled. Totals are never summed across epochs into a single
        headline.
      </p>
    </section>
  );
}
