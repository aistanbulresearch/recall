/**
 * Cohort ledger: the machine-triggered cycles, straight from the EXECUTED
 * manifests exported to the evidence tree (c1, c2 are verbatim copies of
 * artifacts/evidence/cohort-compression/executed-manifests/). Each manifest
 * goes through the same contract-validating view-model builder as every other
 * surface; the ledger renders derived fields only.
 *
 * Cycles that have not executed yet are explicit PENDING placeholders, and
 * the partially-executed day is reported as the line it is, never a headline.
 */

import { useMemo } from 'react';

import c1Manifest from '../../data/c1-manifest.json';
import c2Manifest from '../../data/c2-manifest.json';
import { buildViewModel } from '../../viewmodel/builder';
import type { ArtifactBundle, ViewModel } from '../../viewmodel/types';
import { DerivedValue, fieldToStripEntry, useStripEntries } from '../strip';

const LEDGER_FIELDS = [
  'UI-COHORT-CYCLE-ID',
  'UI-COHORT-SCHEDULE-MODE',
  'UI-COHORT-CYCLES-TOTAL',
  'UI-COHORT-RUNS-TOTAL',
  'UI-COHORT-CASES',
  'UI-COHORT-SOURCE-COMMIT',
  'UI-COHORT-PLAN-SHA256',
  'UI-COHORT-DATA-MODE',
] as const;

function wrap(id: string, manifest: unknown): ArtifactBundle {
  return {
    bundle_id: `cohort-${id}`,
    bundle_kind: 'recall.web.static_artifact_bundle',
    bundle_version: '1.0.0',
    provenance: {
      note: `Verbatim executed manifest export: artifacts/evidence/cohort-compression/executed-manifests/${id}-manifest.json`,
    },
    artifacts: [manifest as ArtifactBundle['artifacts'][number]],
  };
}

function CycleCard({ id, fields }: { id: string; fields: ViewModel }) {
  const chip = (fieldId: string) => (
    <DerivedValue
      entry={{ ...fieldToStripEntry(fields[fieldId]), key: `${id}:${fieldId}` }}
    />
  );
  return (
    <article className="record-card cycle-card">
      <h2>
        Cycle {chip('UI-COHORT-CYCLE-ID')}{' '}
        <span className="cycle-epoch">executed</span>
      </h2>
      <p className="card-line">schedule {chip('UI-COHORT-SCHEDULE-MODE')}</p>
      <p className="card-line">
        cycles in day {chip('UI-COHORT-CYCLES-TOTAL')} · runs {chip('UI-COHORT-RUNS-TOTAL')} ·
        cases {chip('UI-COHORT-CASES')}
      </p>
      <p className="card-line">
        source commit {chip('UI-COHORT-SOURCE-COMMIT')} · plan {chip('UI-COHORT-PLAN-SHA256')}
      </p>
      <p className="card-line">data mode {chip('UI-COHORT-DATA-MODE')}</p>
    </article>
  );
}

export function CohortLedger() {
  const cycles = useMemo(
    () => [
      { id: 'c1', result: buildViewModel(wrap('c1', c1Manifest)) },
      { id: 'c2', result: buildViewModel(wrap('c2', c2Manifest)) },
    ],
    [],
  );

  useStripEntries(
    'cohort',
    cycles.flatMap(({ id, result }) =>
      LEDGER_FIELDS.map((fieldId) => ({
        ...fieldToStripEntry(result.fields[fieldId]),
        key: `${id}:${fieldId}`,
      })),
    ),
  );

  return (
    <section className="cohort-ledger">
      <header className="view-head">
        <h1>Cohort ledger</h1>
        <p className="view-sub">
          Machine-triggered evaluation cycles. Every card renders an executed manifest from the
          evidence tree; nothing on this page is projected.
        </p>
      </header>

      <div className="record-grid">
        {cycles.map(({ id, result }) => (
          <CycleCard key={id} id={id} fields={result.fields} />
        ))}
      </div>

      <div className="work-card">
        <div className="work-row honest-line">
          <div className="work-case">
            <span className="work-title">c3, partially executed day</span>
            <span className="work-meta">
              Three trigger attempts and a typed incomplete day are on the ledger for this cycle;
              its manifest export lands with the morning bundle. Recorded as a line, not a
              headline.
            </span>
          </div>
          <span className="stamp tone-pending">MANIFEST PENDING</span>
        </div>
      </div>

      <div className="work-card pending-block">
        <div className="pending-head">
          <span className="stamp tone-pending">PENDING</span>
          <span>
            Ramp cycles (r1 → r2 → r3) and the final full-cohort re-scan publish with the
            morning bundle. Their parity counters (newly-created vs reused runs) appear only
            with the executed manifests.
          </span>
        </div>
      </div>

      <p className="honesty-footnote">
        Epoch labels stay on every row: a case re-evaluated in a later epoch is the same case
        again, on purpose, run totals are never presented as distinct-case totals.
      </p>
    </section>
  );
}
