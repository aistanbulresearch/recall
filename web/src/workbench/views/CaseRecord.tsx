/**
 * One re-evaluation record, as a clinician reads it: outcome first, then the
 * chain that produced it (agents, citations, privacy), every figure a derived
 * chip whose lineage lands in the substrate strip.
 */

import type { Scenario } from '../Workbench';
import type { ViewModel, ViewField } from '../../viewmodel/types';
import { DerivedValue, fieldToStripEntry, useStripEntries } from '../strip';
import { recordStamp } from './Worklist';

interface BuildResult {
  fields: ViewModel;
}

const RECORD_FIELDS = [
  'UI-POLICY-OUTCOME',
  'UI-POLICY-REASONS',
  'UI-POLICY-MISSING',
  'UI-CITATION-TOTAL',
  'UI-CITATION-VERIFIED',
  'UI-CITATION-STATUS',
  'UI-PRIVACY-STATUS',
  'UI-PRIVACY-OUTBOUND-FIELDS',
  'UI-PRIVACY-RAW-TEXT-EGRESS',
  'UI-PRIVACY-EGRESS-PROFILE',
  'UI-AGENT-ROSTER',
  'UI-AGENT-STATE',
  'UI-GLOBAL-RUN-ID',
  'UI-GLOBAL-MODE',
  'UI-GLOBAL-RUN-STATE',
  'UI-GLOBAL-UPDATED',
] as const;

function chip(fields: ViewModel, id: string) {
  return <DerivedValue entry={fieldToStripEntry(fields[id])} />;
}

function itemsOf(field: ViewField): string[] {
  return field.items.map((item) => (typeof item === 'string' ? item : JSON.stringify(item)));
}

interface RosterEntry {
  role?: string;
  agent_id?: string;
  revision?: string;
  validation_status?: string;
}

/** Compact roster line: a projection of the derived item, nothing added. */
function rosterLine(item: unknown): string {
  if (typeof item !== 'object' || item === null) {
    return String(item);
  }
  const entry = item as RosterEntry;
  if (!entry.role && !entry.agent_id) {
    return JSON.stringify(item);
  }
  return [entry.role, entry.agent_id, entry.revision, entry.validation_status]
    .filter(Boolean)
    .join(' · ');
}

export function CaseRecord({
  scenario,
  result,
}: {
  scenario: Scenario;
  result: BuildResult;
}) {
  const fields = result.fields;
  useStripEntries(
    `case-${scenario.id}`,
    RECORD_FIELDS.map((id) => fieldToStripEntry(fields[id])),
  );

  const stamp = recordStamp(fields);
  const reasons = itemsOf(fields['UI-POLICY-REASONS']);
  const roster = fields['UI-AGENT-ROSTER'].items.map(rosterLine);

  return (
    <section className="case-record">
      <a className="crumb" href="#/">
        ← Worklist
      </a>
      <header className="view-head">
        <h1>{scenario.clinicalLabel}</h1>
        <p className="view-sub">
          Run {chip(fields, 'UI-GLOBAL-RUN-ID')} · data {chip(fields, 'UI-GLOBAL-MODE')} · updated{' '}
          {chip(fields, 'UI-GLOBAL-UPDATED')}
        </p>
      </header>

      <div className={`outcome-banner tone-${stamp.tone}`}>
        <span className="outcome-stamp">{stamp.label}</span>
        <span className="outcome-code">
          gate outcome {chip(fields, 'UI-POLICY-OUTCOME')}
        </span>
        {reasons.length > 0 ? (
          <ul className="outcome-reasons">
            {reasons.map((reason) => (
              <li key={reason}>
                <code>{reason}</code>
              </li>
            ))}
          </ul>
        ) : null}
      </div>

      <div className="record-grid">
        <article className="record-card">
          <h2>Who worked this case</h2>
          <p className="card-note">
            Three roles, separated on purpose: the agent that proposes is never the agent that
            verifies, and neither decides — the deterministic gate does.
          </p>
          <ul className="roster">
            {roster.map((agent) => (
              <li key={agent}>
                <code>{agent}</code>
              </li>
            ))}
          </ul>
          <p className="card-line">Fleet state: {chip(fields, 'UI-AGENT-STATE')}</p>
        </article>

        <article className="record-card">
          <h2>Citation verification</h2>
          <p className="card-note">
            A claim only counts when its citation resolves to captured source bytes.
          </p>
          <p className="card-line">
            {chip(fields, 'UI-CITATION-VERIFIED')} of {chip(fields, 'UI-CITATION-TOTAL')} citations
            verified · status {chip(fields, 'UI-CITATION-STATUS')}
          </p>
        </article>

        <article className="record-card">
          <h2>Privacy at the boundary</h2>
          <p className="card-note">
            The note text never left the laboratory. Outbound traffic is structured fields only,
            checked and receipted.
          </p>
          <p className="card-line">
            status {chip(fields, 'UI-PRIVACY-STATUS')} · outbound fields{' '}
            {chip(fields, 'UI-PRIVACY-OUTBOUND-FIELDS')} · raw-text egress{' '}
            {chip(fields, 'UI-PRIVACY-RAW-TEXT-EGRESS')} · profile{' '}
            {chip(fields, 'UI-PRIVACY-EGRESS-PROFILE')}
          </p>
        </article>
      </div>
    </section>
  );
}
