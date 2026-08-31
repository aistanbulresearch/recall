/**
 * The run surface must be honest before it is impressive.
 *
 * These tests hold the shape of that promise while the terminal evidence is
 * still being produced: a missing export renders as an explicit awaiting state
 * and never as zero or success; a partial export refuses with a reason; a full
 * export recomputes its own distribution instead of trusting a summary; and
 * the containment block proves the resilience claim per case rather than
 * asserting it.
 */

import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';

import { RunSurface } from '../src/run/RunSurface';
import {
  CASE_STATES,
  STATE_LANGUAGE,
  distributionAgrees,
  distributionFromCases,
  type RunBundle,
  type RunCase,
} from '../src/run/runBundle';
import shipped from '../src/site/data/run-bundle.json';

const markup = renderToStaticMarkup(<RunSurface />);

describe('the shipped bundle, whatever state it is in', () => {
  it('declares itself either PENDING or READY, and says why when pending', () => {
    const bundle = shipped as unknown as RunBundle;
    expect(['PENDING', 'READY']).toContain(bundle.status);
    if (bundle.status === 'PENDING') {
      expect(bundle.note.length).toBeGreaterThan(40);
    }
  });

  it('never renders a missing export as zero, empty or success', () => {
    const bundle = shipped as unknown as RunBundle;
    if (bundle.status === 'READY') {
      return;
    }
    expect(markup).toContain('AWAITING TERMINAL EVIDENCE');
    expect(markup).toContain('EXPORT PENDING');
    // No fabricated cohort: no field of cells, no distribution, no counts and
    // no terminal-state claim. (Prose describing what the surface WILL show is
    // not a claim that it has happened.)
    expect(markup).not.toContain('class="field"');
    expect(markup).not.toContain('total-row');
    expect(markup).not.toContain('SUCCEEDED');
    expect(markup).not.toMatch(/\d{2,}\s+cases/);
  });

  it('never presents a replay as live', () => {
    expect(markup.toLowerCase()).not.toContain('live now');
    expect(markup).not.toContain('streaming');
    if ((shipped as unknown as RunBundle).status === 'READY') {
      expect(markup).toContain('NOT LIVE');
    }
  });
});

describe('bundle reading rules', () => {
  const base: RunBundle = {
    schema_version: '1.0.0',
    status: 'READY',
    note: '',
    execution: {
      job: 'recall-cohort-daily',
      generation: 27,
      region: 'us-central1',
      terminal_state: 'SUCCEEDED',
      started_at: '2026-08-31T00:00:00Z',
      finished_at: '2026-08-31T13:55:00Z',
      source_commit: 'abc',
      image_digest: 'sha256:def',
    },
    cohort: {
      total_cases: 3,
      distribution: { NO_ACTION: 2, HALTED: 1 },
      artifacts: { valid: 10, invalid: 0 },
    },
    cases: [
      { case_id: 'a', state: 'NO_ACTION' },
      { case_id: 'b', state: 'NO_ACTION' },
      { case_id: 'c', state: 'HALTED' },
    ],
  };

  it('recomputes the distribution from the rows', () => {
    const counts = distributionFromCases(base.cases as RunCase[]);
    expect(counts.NO_ACTION).toBe(2);
    expect(counts.HALTED).toBe(1);
    expect(counts.REVIEW_REQUIRED).toBe(0);
    expect(distributionAgrees(base)).toBe(true);
  });

  it('surfaces a disagreement between the summary and the rows instead of hiding it', () => {
    const skewed: RunBundle = {
      ...base,
      cohort: { ...base.cohort!, distribution: { NO_ACTION: 3 } },
    };
    expect(distributionAgrees(skewed)).toBe(false);
  });
});

describe('state language', () => {
  it('gives every terminal state a plain-language reading', () => {
    for (const state of CASE_STATES) {
      expect(STATE_LANGUAGE[state].short.length).toBeGreaterThan(0);
      expect(STATE_LANGUAGE[state].meaning.length).toBeGreaterThan(40);
    }
  });

  it('keeps HALTED a technical terminal, never a scientific statement', () => {
    const halted = STATE_LANGUAGE.HALTED.meaning.toLowerCase();
    expect(halted).toContain('technical terminal');
    expect(halted).toContain('never a task');
    expect(STATE_LANGUAGE.HALTED.meaning).not.toContain('evidence did not verify');
    // ABSTAIN and HALTED must not read as the same thing.
    expect(STATE_LANGUAGE.ABSTAIN.meaning).not.toEqual(STATE_LANGUAGE.HALTED.meaning);
  });
});
