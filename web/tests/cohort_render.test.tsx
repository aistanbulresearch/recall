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
import example from './fixtures/cohort-day2-manifest.example.json';

const golden = goldenBundle as unknown as ArtifactBundle;

// The real example's own anchor, so the rendered chain is the chain the
// producer actually emits rather than one this lane made up.
const ANCHOR = example.vcv_anchors[0];

/**
 * The REAL contract example with overrides, so these rendering tests cannot
 * drift into describing a manifest shape nobody emits.
 */
function manifest(overrides: Record<string, unknown> = {}) {
  return { ...example, ...overrides };
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
    expect(markup).toContain('data-field-id="UI-COHORT-RUNS-DELTA"');
    expect(markup).toContain('data-field-id="UI-COHORT-RUNS-TOTAL"');
    expect(markup).toContain('data-field-id="UI-COHORT-CYCLES-TOTAL"');
  });

  it('shows which code produced the day, beside the data mode of the manifest', () => {
    const markup = renderWith([manifest()]);
    expect(markup).toContain('data-field-id="UI-COHORT-IMAGE-DIGEST"');
    expect(markup).toContain(example.image_digest);
    // A synthetic manifest carries a sentinel digest, so the mode travels with
    // it and a sentinel can never read as a deployed artifact.
    expect(markup).toContain('data-field-id="UI-COHORT-DATA-MODE"');
    expect(markup).toContain('sentinel digest');
  });

  it('says the totals reconcile against the history they came from', () => {
    const markup = renderWith([manifest()]);
    expect(markup).toContain('data-agrees="true"');
  });

  it('says so when the totals disagree with the manifest own history', () => {
    const markup = renderWith([
      manifest({ cumulative: { ...example.cumulative, daily_cycles: 99 } }),
    ]);
    expect(markup).toContain('data-agrees="false"');
    expect(markup).toContain('disagree');
    expect(markup).toContain('daily cycles');
  });

  it('labels each case with its own declared mode, not one badge for all', () => {
    const markup = renderWith([manifest()]);
    // Both modes the 2.0.0 contract permits are present in the real example.
    expect(markup).toContain('data-mode="SYNTHETIC_WITH_CAPTURED_REPLAY"');
    expect(markup).toContain('data-mode="SYNTHETIC_ONLY"');
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
        cases: [
          { case_id: 'orphan', data_mode: 'SYNTHETIC_WITH_CAPTURED_REPLAY', vcv: 'VCV999999999' },
        ],
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

  it('withholds the sentence when selection was pinned to one date', () => {
    // Four wakeups, one selection date. The strongest reason this panel exists.
    const markup = renderWith([
      manifest({
        execution_history: [
          {
            day_index: 1,
            executed_at: '2026-08-25T06:00:00Z',
            selected_for_date: '2026-08-25',
            runs_created: 3,
            runs_predicted: 3,
          },
          {
            day_index: 2,
            executed_at: '2026-08-26T06:00:00Z',
            selected_for_date: '2026-08-25',
            runs_created: 0,
            runs_predicted: 0,
          },
        ],
      }),
    ]);
    expect(markup).toContain('data-proven="false"');
    expect(markup).not.toContain('of operation');
    expect(markup).toContain('selected work for a different date than it ran');
  });

  it('falls back to counting cycles when two runs share a date', () => {
    const markup = renderWith([
      manifest({
        execution_history: [
          {
            day_index: 1,
            executed_at: '2026-08-25T19:00:00Z',
            selected_for_date: '2026-08-25',
            runs_created: 3,
            runs_predicted: 3,
          },
          {
            day_index: 2,
            executed_at: '2026-08-25T21:00:00Z',
            selected_for_date: '2026-08-25',
            runs_created: 3,
            runs_predicted: 3,
          },
        ],
      }),
    ]);
    expect(markup).toContain('daily cycles recorded');
    expect(markup).toContain('data-proven="false"');
    expect(markup).not.toContain('of operation');
    expect(markup).toContain('two runs share a calendar date');
  });

  it('names an incomplete day and its failure receipt on screen', () => {
    const markup = renderWith([
      manifest({
        execution_history: [
          ...example.execution_history,
          {
            day_index: 3,
            executed_at: null,
            selected_for_date: '2026-08-27',
            runs_created: 0,
            runs_predicted: 3,
            execution_status: 'INCOMPLETE',
            failure_receipt_id: '11111111-1111-5111-8111-111111111111',
          },
        ],
      }),
    ]);
    expect(markup).toContain('Day 3 did not complete');
    expect(markup).toContain('11111111-1111-5111-8111-111111111111');
    // The claim the completed days carry still renders, with the incomplete
    // day named rather than hidden.
    expect(markup).toContain('data-proven="true"');
    expect(markup).toContain('1 incomplete attempt');
  });

  it('refuses every figure when two day manifests are present', () => {
    const markup = renderWith([
      manifest({ artifact_id: 'day-1', day_index: 1 }),
      manifest({ artifact_id: 'day-2', day_index: 2 }),
    ]);
    expect(markup).toContain('could not be attributed to a specific day');
    expect(markup).not.toContain('data-field-id="UI-COHORT-RUNS-TOTAL"');
    expect(markup).not.toContain('data-field-id="UI-COHORT-CYCLES-TOTAL"');
  });
});
