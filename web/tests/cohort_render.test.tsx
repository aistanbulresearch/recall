/**
 * Cohort panel rendering.
 *
 * The derivation tests prove what the panel is entitled to say. These prove
 * what actually reaches the screen, which is the thing a judge sees and the
 * only thing a screen recording can capture.
 */

import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';

import goldenBundle from '../src/bundles/golden.json';
import { CohortPanel } from '../src/components/CohortPanel';
import { buildViewModel } from '../src/viewmodel/builder';
import type { ArtifactBundle } from '../src/viewmodel/types';

const golden = goldenBundle as unknown as ArtifactBundle;

const ANCHOR = {
  vcv: 'VCV002895953',
  capture_path: 'artifacts/captures/rcl-205/a.xlsx',
  sha256: 'abc123def456',
};

function manifest(overrides: Record<string, unknown> = {}) {
  return {
    artifact_id: String(overrides.artifact_id ?? 'manifest-1'),
    case_id: null,
    content_hash: 'f'.repeat(64),
    created_at: '2026-08-26T06:00:00Z',
    data_mode: 'SYNTHETIC_WITH_CAPTURED_REPLAY',
    extensions: {},
    input_artifact_ids: [],
    producer: { component: 'cohort-builder', identity: 'cohort', version: '1.0.0' },
    run_id: null,
    schema_name: 'CohortDayManifest',
    schema_version: '1.0.0',
    signature_ref: null,
    status: 'VALID',
    warnings: [],
    day_index: 2,
    delta: { cases_watched: 9, runs_created: 9 },
    cumulative: { cases_watched: 12, runs_created: 15 },
    cases: [
      { case_id: 'case-anchored', data_mode: 'SYNTHETIC_WITH_CAPTURED_REPLAY', vcv: ANCHOR.vcv },
      { case_id: 'case-plain', data_mode: 'SYNTHETIC' },
    ],
    vcv_anchors: [ANCHOR],
    execution_history: [
      { day_index: 1, executed_at: '2026-08-25T06:00:00Z' },
      { day_index: 2, executed_at: '2026-08-26T06:00:00Z' },
    ],
    ...overrides,
  };
}

function renderWith(artifacts: unknown[]): string {
  const bundle = { ...golden, artifacts: [...golden.artifacts, ...artifacts] } as ArtifactBundle;
  return renderToStaticMarkup(<CohortPanel model={buildViewModel(bundle).fields} />);
}

describe('cohort panel rendering', () => {
  it('renders nothing at all when no manifest is present', () => {
    const markup = renderToStaticMarkup(<CohortPanel model={buildViewModel(golden).fields} />);
    expect(markup).toBe('');
  });

  it('shows the delta and the running total as separate figures', () => {
    const markup = renderWith([manifest()]);
    expect(markup).toContain('data-field-id="UI-COHORT-CASES-DELTA"');
    expect(markup).toContain('data-field-id="UI-COHORT-CASES-TOTAL"');
    expect(markup).toContain('data-field-id="UI-COHORT-RUNS-TOTAL"');
    expect(markup).toContain('>12<');
    expect(markup).toContain('>15<');
  });

  it('labels each case with its own declared mode, not one badge for all', () => {
    const markup = renderWith([manifest()]);
    expect(markup).toContain('data-mode="SYNTHETIC_WITH_CAPTURED_REPLAY"');
    expect(markup).toContain('data-mode="SYNTHETIC"');
    expect(markup).toContain('data-anchored="true"');
    expect(markup).toContain('data-anchored="false"');
  });

  it('puts the accession, its capture file and its hash in one place', () => {
    const markup = renderWith([manifest()]);
    const chain = markup.slice(markup.indexOf(ANCHOR.vcv));
    expect(chain).toContain(ANCHOR.capture_path);
    expect(chain).toContain(ANCHOR.sha256);
  });

  it('marks an accession with no anchor rather than showing it bare', () => {
    const markup = renderWith([
      manifest({
        cases: [{ case_id: 'orphan', data_mode: 'SYNTHETIC', vcv: 'VCV999999999' }],
        vcv_anchors: [],
      }),
    ]);
    expect(markup).toContain('no capture anchor');
    expect(markup).toContain('cannot be');
  });

  it('speaks the elapsed-days sentence only when the timestamps prove it', () => {
    const proven = renderWith([manifest()]);
    expect(proven).toContain('Day 2 of operation');
    expect(proven).toContain('data-proven="true"');
  });

  it('falls back to counting cycles when two runs share a date', () => {
    const markup = renderWith([
      manifest({
        execution_history: [
          { day_index: 1, executed_at: '2026-08-25T19:00:00Z' },
          { day_index: 2, executed_at: '2026-08-25T21:00:00Z' },
        ],
      }),
    ]);
    expect(markup).toContain('daily cycles recorded');
    expect(markup).toContain('data-proven="false"');
    expect(markup).not.toContain('of operation');
    expect(markup).toContain('two runs share a calendar date');
  });

  it('refuses every figure when two day manifests are present', () => {
    const markup = renderWith([
      manifest({ artifact_id: 'day-1', day_index: 1 }),
      manifest({ artifact_id: 'day-2', day_index: 2 }),
    ]);
    expect(markup).toContain('could not be attributed to a specific day');
    expect(markup).not.toContain('data-field-id="UI-COHORT-CASES-TOTAL"');
    expect(markup).not.toContain('>12<');
  });
});
