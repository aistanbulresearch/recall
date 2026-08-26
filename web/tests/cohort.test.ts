/**
 * Cohort panel behaviour.
 *
 * The counter is the number a judge will read as the claim, so the tests that
 * matter most are the ones that hold the claim BELOW what the data proves:
 * four runs in one evening must not be describable as four days of operation,
 * and an accession number must not appear without the capture it is anchored to.
 */

import { describe, expect, it } from 'vitest';

import { buildViewModel } from '../src/viewmodel/builder';
import {
  anchorFor,
  caseModeCopy,
  operationSpan,
  unanchoredVcvs,
} from '../src/viewmodel/cohort';
import type { ArtifactBundle } from '../src/viewmodel/types';
import example from './fixtures/cohort-day2-manifest.example.json';

/**
 * A day that genuinely advanced the cohort: it ran on a date, selected work FOR
 * that same date, and the selection produced runs.
 */
function execution(day: number, at: string, overrides: Record<string, unknown> = {}) {
  return {
    day_index: day,
    executed_at: at,
    selected_for_date: at.slice(0, 10),
    runs_created: 3,
    runs_predicted: 3,
    ...overrides,
  };
}

const FOUR_REAL_DAYS = [
  execution(1, '2026-08-25T06:00:00Z'),
  execution(2, '2026-08-26T06:00:00Z'),
  execution(3, '2026-08-27T06:00:00Z'),
  execution(4, '2026-08-28T06:00:00Z'),
];

describe('elapsed days are proven, never assumed', () => {
  it('claims the span when four distinct dates are in order', () => {
    const span = operationSpan(FOUR_REAL_DAYS);
    expect(span.proven).toBe(true);
    expect(span.distinctDays).toBe(4);
    expect(span.withheldBecause).toBeNull();
    expect(span.sentence).toContain('Day 4 of operation');
    expect(span.sentence).toContain('4 distinct days');
  });

  it('refuses the span when four runs share one evening', () => {
    const span = operationSpan([
      execution(1, '2026-08-25T19:00:00Z'),
      execution(2, '2026-08-25T20:00:00Z'),
      execution(3, '2026-08-25T21:00:00Z'),
      execution(4, '2026-08-25T22:00:00Z'),
    ]);
    expect(span.proven).toBe(false);
    expect(span.withheldBecause).toBe('two runs share a calendar date');
    expect(span.sentence).toBe('4 daily cycles recorded.');
    expect(span.sentence).not.toContain('operation');
  });

  it('refuses when day order and execution order disagree', () => {
    const span = operationSpan([
      execution(1, '2026-08-26T06:00:00Z'),
      execution(2, '2026-08-25T06:00:00Z'),
    ]);
    expect(span.proven).toBe(false);
    expect(span.withheldBecause).toBe('day order and execution order disagree');
  });

  it('refuses when a timestamp does not parse, rather than skipping it', () => {
    const span = operationSpan([execution(1, 'sometime tuesday'), execution(2, '2026-08-26T06:00:00Z')]);
    expect(span.proven).toBe(false);
    expect(span.withheldBecause).toBe('an execution timestamp did not parse');
  });

  it('refuses when an execution carries no day index', () => {
    const span = operationSpan([
      { executed_at: '2026-08-25T06:00:00Z' },
      execution(2, '2026-08-26T06:00:00Z'),
    ]);
    expect(span.proven).toBe(false);
    expect(span.withheldBecause).toBe('an execution carried no day index');
  });

  it('does not call a single run a span', () => {
    const span = operationSpan([execution(1, '2026-08-25T06:00:00Z')]);
    expect(span.proven).toBe(false);
    expect(span.sentence).toBe('1 daily cycle recorded.');
  });

  it('says nothing at all when there is no execution record', () => {
    const span = operationSpan([]);
    expect(span.cycles).toBe(0);
    expect(span.proven).toBe(false);
    expect(span.withheldBecause).toBe('no execution record');
  });

  it('refuses when selection is pinned to a date the day did not run on', () => {
    // The date-pinned failure: execution dates advance, selection does not, so
    // days 2-4 create runs that still belong to day 1. Timestamps alone pass.
    const span = operationSpan([
      execution(1, '2026-08-25T06:00:00Z', { selected_for_date: '2026-08-25' }),
      execution(2, '2026-08-26T06:00:00Z', { selected_for_date: '2026-08-25' }),
      execution(3, '2026-08-27T06:00:00Z', { selected_for_date: '2026-08-25' }),
    ]);
    expect(span.proven).toBe(false);
    expect(span.withheldBecause).toBe('a day selected work for a different date than it ran');
    // The distinct dates are real; they are just not evidence of cohort days.
    expect(span.distinctDays).toBe(3);
  });

  it('refuses when a day does not say what date it selected for', () => {
    const span = operationSpan([
      execution(1, '2026-08-25T06:00:00Z'),
      execution(2, '2026-08-26T06:00:00Z', { selected_for_date: undefined }),
    ]);
    expect(span.proven).toBe(false);
    expect(span.withheldBecause).toBe('a day did not declare the date its selection was driven by');
  });

  it('refuses when a day woke up and created nothing it had predicted', () => {
    const span = operationSpan([
      execution(1, '2026-08-25T06:00:00Z'),
      execution(2, '2026-08-26T06:00:00Z', { runs_created: 0, runs_predicted: 4 }),
    ]);
    expect(span.proven).toBe(false);
    expect(span.withheldBecause).toBe('a day created no runs and none were predicted');
  });

  it('refuses when a day records no selection evidence at all', () => {
    const span = operationSpan([
      execution(1, '2026-08-25T06:00:00Z'),
      execution(2, '2026-08-26T06:00:00Z', { runs_created: undefined }),
    ]);
    expect(span.proven).toBe(false);
    expect(span.withheldBecause).toBe('a day recorded no selection evidence');
  });

  it('accepts a quiet day that pre-committed to creating nothing', () => {
    // Zero runs is a real cohort day when zero was predicted before it ran. It
    // is only suspicious when the day expected work and produced none.
    const span = operationSpan([
      execution(1, '2026-08-25T06:00:00Z'),
      execution(2, '2026-08-26T06:00:00Z', { runs_created: 0, runs_predicted: 0 }),
    ]);
    expect(span.proven).toBe(true);
    expect(span.sentence).toContain('Day 2 of operation');
  });

  it('passes a row whose timestamp is value-level wrong, and that is the limit', () => {
    // The real DAY1_HISTORY row as committed on 2026-08-25 carried the SECOND
    // execution's timestamp standing in for the day's own run. These are its
    // actual values. Every check here passes: the dates are distinct, the order
    // holds, and selected_for_date agrees with executed_at's date.
    //
    // The pass is correct and the pass is the point. This gate proves the
    // history is INTERNALLY CONSISTENT. It cannot prove the history agrees with
    // the evidence it describes, because nothing here compares a row against the
    // frozen record of the run it claims to report. A wrong value that is
    // internally consistent is invisible to every check in this file.
    //
    // So this test exists to stop someone reading a green gate as coverage it
    // does not have. The fix for that class belongs upstream, in sourcing the
    // row from the evidence, not in a downstream panel guessing.
    const span = operationSpan([
      {
        day_index: 1,
        executed_at: '2026-08-25T15:01:07Z',
        selected_for_date: '2026-08-25',
        runs_created: 3,
        runs_predicted: 3,
      },
      execution(2, '2026-08-26T16:00:00Z'),
    ]);
    expect(span.proven).toBe(true);
    expect(span.withheldBecause).toBeNull();
  });

  it('counts cycles truthfully even when it withholds the span', () => {
    for (const runs of [FOUR_REAL_DAYS, FOUR_REAL_DAYS.slice(0, 2)]) {
      expect(operationSpan(runs).cycles).toBe(runs.length);
    }
  });
});

describe('a case declares its own composition', () => {
  it('says an anchored case is synthetic and what it is anchored to', () => {
    const copy = caseModeCopy('SYNTHETIC_WITH_CAPTURED_REPLAY');
    expect(copy.anchored).toBe(true);
    expect(copy.plain).toContain('Synthetic');
    expect(copy.plain).toContain('captured');
  });

  it('never describes a record as a patient', () => {
    for (const mode of [
      'SYNTHETIC_WITH_CAPTURED_REPLAY',
      'CAPTURED_REPLAY',
      'SYNTHETIC',
      'MOCK',
      'ANYTHING_ELSE',
    ]) {
      expect(caseModeCopy(mode).plain.toLowerCase()).not.toContain('patient');
      expect(caseModeCopy(mode).plain.toLowerCase()).not.toContain('clinical');
    }
  });

  it('does not call an unanchored case anchored', () => {
    expect(caseModeCopy('SYNTHETIC').anchored).toBe(false);
    expect(caseModeCopy(undefined).anchored).toBe(false);
    expect(caseModeCopy(undefined).plain).toContain('not declared');
  });
});

describe('every accession number carries its chain', () => {
  const anchors = [
    { vcv: 'VCV002895953', capture_path: 'artifacts/captures/rcl-205/a.xlsx', sha256: 'abc123' },
  ];

  it('resolves a VCV to its capture file and hash in one step', () => {
    const anchor = anchorFor('VCV002895953', anchors);
    expect(anchor?.capture_path).toBe('artifacts/captures/rcl-205/a.xlsx');
    expect(anchor?.sha256).toBe('abc123');
  });

  it('reports an unmatched VCV rather than resolving it to something else', () => {
    expect(anchorFor('VCV999999999', anchors)).toBeNull();
    expect(anchorFor('', anchors)).toBeNull();
    expect(anchorFor(undefined, anchors)).toBeNull();
  });

  it('names every case whose accession cannot be traced', () => {
    const cases = [
      { case_id: 'c1', vcv: 'VCV002895953' },
      { case_id: 'c2', vcv: 'VCV999999999' },
      { case_id: 'c3' },
    ];
    expect(unanchoredVcvs(cases, anchors)).toEqual(['VCV999999999']);
  });

  it('does not flag synthetic cases that claim no accession', () => {
    expect(unanchoredVcvs([{ case_id: 'c3' }, { case_id: 'c4', vcv: '' }], anchors)).toEqual([]);
  });
});

/* ---------------------------------------------------------------- view model */

/**
 * Built from the REAL contract example rather than a shape this lane invented,
 * so a producer-side change breaks in one place instead of silently leaving
 * these fixtures describing a manifest nobody emits.
 */
function manifestArtifact(overrides: Record<string, unknown> = {}) {
  return { ...example, ...overrides };
}

function bundleWith(artifacts: unknown[]): ArtifactBundle {
  return {
    bundle_id: 'test-bundle',
    bundle_kind: 'DEMO',
    bundle_version: '1.0.0',
    provenance: {},
    artifacts,
  } as unknown as ArtifactBundle;
}

describe('cohort fields resolve from the manifest', () => {
  it('reads the totals from the manifest rather than counting them here', () => {
    const { fields } = buildViewModel(bundleWith([manifestArtifact()]));
    // Asserted against the example's own values, so these cannot drift from the
    // contract without this failing.
    expect(fields['UI-COHORT-DAY-INDEX'].value).toBe(example.day_index);
    expect(fields['UI-COHORT-RUNS-TOTAL'].value).toBe(example.cumulative.runs_created);
    expect(fields['UI-COHORT-CYCLES-TOTAL'].value).toBe(example.cumulative.daily_cycles);
    // The running total is NOT the length of the case list this day happens to
    // carry, and the panel must never silently reconcile the two.
    expect(fields['UI-COHORT-CASES'].items).toHaveLength(example.cases.length);
  });

  it('carries lineage for every cohort value it shows', () => {
    const { fields } = buildViewModel(bundleWith([manifestArtifact()]));
    for (const id of ['UI-COHORT-DAY-INDEX', 'UI-COHORT-CYCLES-TOTAL', 'UI-COHORT-VCV-ANCHORS']) {
      expect(fields[id].status, id).toBe('KNOWN');
      expect(fields[id].source_refs.length, id).toBeGreaterThan(0);
    }
  });

  it('hides every cohort field when no manifest is present', () => {
    const { fields } = buildViewModel(bundleWith([]));
    for (const id of ['UI-COHORT-DAY-INDEX', 'UI-COHORT-CYCLES-TOTAL', 'UI-COHORT-CASES']) {
      expect(fields[id].status, id).toBe('UNKNOWN');
      expect(fields[id].value, id).toBeNull();
      expect(fields[id].hidden, id).toBe(true);
    }
  });

  it('makes a second day manifest detectable rather than silently preferred', () => {
    const bundle = bundleWith([
      manifestArtifact({ artifact_id: 'day-1', day_index: 1 }),
      manifestArtifact({ artifact_id: 'day-2', day_index: 2 }),
    ]);
    const { fields } = buildViewModel(bundle);
    // The scalar resolves from the FIRST match, which is why the panel refuses:
    // this count is what lets it notice.
    expect(fields['UI-COHORT-MANIFEST-DAYS'].items).toHaveLength(2);
  });

  it('rejects a manifest declaring an unsupported version', () => {
    const { fields, rejected } = buildViewModel(
      bundleWith([manifestArtifact({ schema_version: '4.0.0' })]),
    );
    expect(rejected[0]?.reason_code).toBe('contract_major_unsupported');
    expect(fields['UI-COHORT-DAY-INDEX'].status).toBe('UNKNOWN');
  });
});
