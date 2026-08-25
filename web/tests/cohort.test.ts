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

function execution(day: number, at: string) {
  return { day_index: day, executed_at: at };
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

function manifestArtifact(overrides: Record<string, unknown> = {}) {
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
    cases: [{ case_id: 'c1', data_mode: 'SYNTHETIC_WITH_CAPTURED_REPLAY', vcv: 'VCV002895953' }],
    vcv_anchors: [
      { vcv: 'VCV002895953', capture_path: 'artifacts/captures/rcl-205/a.xlsx', sha256: 'abc123' },
    ],
    execution_history: FOUR_REAL_DAYS.slice(0, 2),
    ...overrides,
  };
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
    // renderScalar preserves numbers as numbers, so these stay numeric.
    expect(fields['UI-COHORT-DAY-INDEX'].value).toBe(2);
    expect(fields['UI-COHORT-CASES-DELTA'].value).toBe(9);
    expect(fields['UI-COHORT-CASES-TOTAL'].value).toBe(12);
    expect(fields['UI-COHORT-RUNS-TOTAL'].value).toBe(15);
    // The manifest lists one case but reports twelve watched. The panel must
    // not silently "correct" the total to the length of the list it can see.
    expect(fields['UI-COHORT-CASES'].items).toHaveLength(1);
  });

  it('carries lineage for every cohort value it shows', () => {
    const { fields } = buildViewModel(bundleWith([manifestArtifact()]));
    for (const id of ['UI-COHORT-DAY-INDEX', 'UI-COHORT-CASES-TOTAL', 'UI-COHORT-VCV-ANCHORS']) {
      expect(fields[id].status, id).toBe('KNOWN');
      expect(fields[id].source_refs.length, id).toBeGreaterThan(0);
    }
  });

  it('hides every cohort field when no manifest is present', () => {
    const { fields } = buildViewModel(bundleWith([]));
    for (const id of ['UI-COHORT-DAY-INDEX', 'UI-COHORT-CASES-TOTAL', 'UI-COHORT-CASES']) {
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
      bundleWith([manifestArtifact({ schema_version: '2.0.0' })]),
    );
    expect(rejected[0]?.reason_code).toBe('contract_major_unsupported');
    expect(fields['UI-COHORT-DAY-INDEX'].status).toBe('UNKNOWN');
  });
});
