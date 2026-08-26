/**
 * CohortDayManifest 3.0.0, the compressed-session contract.
 *
 * NO producer example is committed for 3.0.0 (checked at 740fc36: the example
 * directory still holds only 2.x files), so this fixture is LANE-AUTHORED from
 * the shipped parser's rules in scheduler_v3.py. Two row groups are the
 * exception: the day-1 row and the failed-tick row copy the exact values
 * _legacy_prefix_is_exact pins in the contract, so those bytes are
 * producer-pinned even though the file is not. The first real c1 manifest
 * replaces this authorship gap tonight via the REAL_MANIFEST check.
 */

import { describe, expect, it } from 'vitest';

import { buildViewModel } from '../src/viewmodel/builder';
import {
  COMPRESSED_SCHEDULE_MODE,
  historyAgreement,
  isCompressedRow,
  operationSpan,
  scheduleModeCopy,
} from '../src/viewmodel/cohort';
import type { ArtifactBundle } from '../src/viewmodel/types';

/** The exact day-1 row the contract pins, verbatim from _legacy_prefix_is_exact. */
const DAY1_ROW = {
  sequence_index: 1,
  source_schema_version: 'CohortHistoryReceipt/1.0.0',
  cycle_id: null,
  cycle_index: null,
  cohort_due_date: '2026-08-25',
  scheduled_for: '2026-08-25T15:00:00Z',
  window_start: null,
  window_end: null,
  trigger_code: 'DAY1_MANUAL',
  executed_at: '2026-08-25T15:00:03.280432Z',
  runs_created: 1,
  runs_predicted: 1,
  execution_status: 'COMPLETE',
  failure_receipt_id: null,
  evidence_state: 'LIVE_INFRASTRUCTURE_SYNTHETIC_DATA',
  schedule_mode: null,
};

/** The exact failed-tick row the contract pins. */
const FAILURE_ROW = {
  sequence_index: 2,
  source_schema_version: 'CompressedCycleFailureReceipt/1.0.0',
  cycle_id: null,
  cycle_index: null,
  cohort_due_date: '2026-08-26',
  scheduled_for: '2026-08-26T16:00:00Z',
  window_start: null,
  window_end: null,
  trigger_code: 'COHORT_DAY_MANAGED',
  executed_at: null,
  runs_created: 0,
  runs_predicted: 3,
  execution_status: 'INCOMPLETE',
  failure_receipt_id: '22222222-2222-5222-8222-222222222222',
  evidence_state: 'OWNER_REPORTED',
  schedule_mode: null,
};

function compressedRow(cycle: number, executedAt: string, runs: number) {
  const windowStart = executedAt.slice(0, 17) + '00Z';
  return {
    sequence_index: cycle + 2,
    source_schema_version: 'CohortDayManifest/3.0.0',
    cycle_id: `c${cycle}`,
    cycle_index: cycle,
    cohort_due_date: '2026-08-26',
    scheduled_for: windowStart,
    window_start: windowStart,
    window_end: '2026-08-26T23:59:00Z',
    trigger_code: 'COHORT_COMPRESSED_MACHINE_TRIGGERED',
    executed_at: executedAt,
    runs_created: runs,
    runs_predicted: runs,
    execution_status: 'COMPLETE',
    failure_receipt_id: null,
    evidence_state: 'LIVE_INFRASTRUCTURE_SYNTHETIC_DATA',
    schedule_mode: COMPRESSED_SCHEDULE_MODE,
  };
}

const HISTORY = [
  DAY1_ROW,
  FAILURE_ROW,
  compressedRow(1, '2026-08-26T20:30:12Z', 3),
  compressedRow(2, '2026-08-26T21:00:09Z', 2),
];

const CUMULATIVE = {
  compressed_cycles_completed: 2,
  successful_compressed_cycles: 2,
  runs_predicted: 5,
  runs_created: 5,
  distinct_execution_dates: 1,
  logical_days_covered: 1,
  historical_incomplete_attempts: 1,
};

function v3Manifest(overrides: Record<string, unknown> = {}) {
  return {
    artifact_id: String(overrides.artifact_id ?? 'v3-manifest-1'),
    case_id: null,
    content_hash: 'f'.repeat(64),
    created_at: '2026-08-26T21:00:09Z',
    data_mode: 'SYNTHETIC_WITH_CAPTURED_REPLAY',
    extensions: {},
    input_artifact_ids: ['22222222-2222-5222-8222-222222222222'],
    producer: { component: 'compressed-scheduler', identity: 'scheduler', version: '3.0.0' },
    run_id: null,
    schema_name: 'CohortDayManifest',
    schema_version: '3.0.0',
    signature_ref: null,
    status: 'VALID',
    warnings: [],
    day_index: 3,
    selected_for_date: '2026-08-26',
    scheduled_for: '2026-08-26T21:00:00Z',
    source_commit: '347f935'.padEnd(40, '0'),
    image_digest: `sha256:${'a'.repeat(64)}`,
    trigger_code: 'COHORT_COMPRESSED_MACHINE_TRIGGERED',
    previous_manifest_id: 'v3-manifest-0',
    managed_history_starts_at_day_index: 2,
    cycle_id: 'c2',
    cycle_index: 2,
    plan_version: 'COMPRESSED_PREDICTION_PLAN_V2',
    plan_sha256: '93393476b4162f0cd6036048d3e5692c6ae1b91f1ede74b6911f80c56930531b',
    cohort_due_date: '2026-08-26',
    window_start: '2026-08-26T21:00:00Z',
    window_end: '2026-08-26T23:59:00Z',
    schedule_mode: COMPRESSED_SCHEDULE_MODE,
    headroom_receipt_id: null,
    delta: {
      selected_case_ids: ['00000000-0000-5000-8000-000000000010'],
      excluded_case_ids: [],
      newly_created_run_ids: ['00000000-0000-5000-8000-000000000020'],
      reused_run_ids: [],
      authoritative_run_ids: ['00000000-0000-5000-8000-000000000020'],
      runs_predicted: 2,
      prediction_match: true,
    },
    cumulative: CUMULATIVE,
    cases: [
      {
        case_id: '00000000-0000-5000-8000-000000000010',
        data_mode: 'SYNTHETIC_ONLY',
        vcv: null,
      },
    ],
    vcv_anchors: [],
    execution_history: HISTORY,
    ...overrides,
  };
}

describe('3.0.0 acceptance', () => {
  it('accepts a 3.0.0 manifest and resolves the new fields', () => {
    const { fields, rejected } = buildViewModel({
      bundle_id: 'v3',
      bundle_kind: 'DEMO',
      bundle_version: '1.0.0',
      provenance: {},
      artifacts: [v3Manifest()],
    } as unknown as ArtifactBundle);
    expect(rejected).toEqual([]);
    expect(fields['UI-COHORT-SCHEDULE-MODE'].value).toBe(COMPRESSED_SCHEDULE_MODE);
    expect(fields['UI-COHORT-CYCLE-ID'].value).toBe('c2');
    expect(fields['UI-COHORT-PLAN-SHA256'].status).toBe('KNOWN');
    expect(fields['UI-COHORT-COMPRESSED-TOTAL'].value).toBe(2);
  });

  it('still accepts the legacy versions beside it', () => {
    // 2.0.0 and 2.1.0 remain historical reads, mirroring the producer's map.
    for (const version of ['2.0.0', '2.1.0', '3.0.0']) {
      const { rejected } = buildViewModel({
        bundle_id: 'v',
        bundle_kind: 'DEMO',
        bundle_version: '1.0.0',
        provenance: {},
        artifacts: [{ ...v3Manifest(), schema_version: version }],
      } as unknown as ArtifactBundle);
      expect(rejected, version).toEqual([]);
    }
  });
});

describe('the label rides on the artifact field', () => {
  it('maps the pinned declaration to the exact wording', () => {
    expect(scheduleModeCopy(COMPRESSED_SCHEDULE_MODE)).toBe(
      'Machine-triggered accelerated schedule (supervised verification)',
    );
  });

  it('gives an undeclared mode no label at all rather than a guessed one', () => {
    expect(scheduleModeCopy(undefined)).toBeNull();
    expect(scheduleModeCopy('SOMETHING_ELSE')).toBeNull();
  });
});

describe('the span with declared compressed cycles', () => {
  it('proves the mixed history and names every row class', () => {
    const span = operationSpan(HISTORY);
    expect(span.proven).toBe(true);
    expect(span.sentence).toContain('1 completed day on distinct dates');
    expect(span.sentence).toContain('2 cycles in the declared machine-triggered compressed session');
    expect(span.sentence).toContain('1 incomplete attempt with a typed failure receipt');
  });

  it('declared date-sharing is not a withhold: the fake-compression guard is scoped', () => {
    // Two compressed cycles share 2026-08-26 and the span still proves,
    // BECAUSE they are declared. The next test is the other half.
    const span = operationSpan(HISTORY);
    expect(span.withheldBecause).toBeNull();
  });

  it('UNDECLARED date-sharing still withholds, so compression cannot be faked', () => {
    const undeclared = HISTORY.map((row) =>
      row.schedule_mode === COMPRESSED_SCHEDULE_MODE ? { ...row, schedule_mode: null } : row,
    );
    const span = operationSpan(undeclared);
    expect(span.proven).toBe(false);
    expect(span.withheldBecause).toBe('two runs share a calendar date');
  });

  it('withholds when a compressed cycle ran outside its declared window', () => {
    const span = operationSpan([
      DAY1_ROW,
      FAILURE_ROW,
      { ...compressedRow(1, '2026-08-27T00:30:00Z', 3), window_end: '2026-08-26T23:59:00Z' },
    ]);
    expect(span.proven).toBe(false);
    expect(span.withheldBecause).toBe('a compressed cycle ran outside its declared window');
  });

  it('withholds when a compressed cycle missed its pre-committed prediction', () => {
    const bad = { ...compressedRow(1, '2026-08-26T20:30:12Z', 3), runs_predicted: 4 };
    const span = operationSpan([DAY1_ROW, FAILURE_ROW, bad]);
    expect(span.proven).toBe(false);
    expect(span.withheldBecause).toBe('a compressed cycle missed its pre-committed prediction');
  });

  it('withholds when a compressed cycle carries no trigger evidence', () => {
    const bad = { ...compressedRow(1, '2026-08-26T20:30:12Z', 3), trigger_code: '' };
    const span = operationSpan([DAY1_ROW, FAILURE_ROW, bad]);
    expect(span.proven).toBe(false);
    expect(span.withheldBecause).toBe('a compressed cycle carries no trigger evidence');
  });

  it('the failed tick renders as a row-level fact, never a heading claim', () => {
    // The contract makes the failure row mandatory in every v3 manifest; the
    // span counts it as an incomplete attempt with its typed receipt.
    const span = operationSpan(HISTORY);
    expect(span.cycles).toBe(4);
    expect(HISTORY.filter((row) => row.execution_status === 'INCOMPLETE')).toHaveLength(1);
  });

  it('day-1 keeps its manual trigger honestly: machine-trigger is per-row, not program-wide', () => {
    expect(DAY1_ROW.trigger_code).toBe('DAY1_MANUAL');
    expect(isCompressedRow(DAY1_ROW)).toBe(false);
  });
});

describe('v3 totals agreement mirrors the shipped derivation', () => {
  it('agrees on the lane-authored history', () => {
    const check = historyAgreement(HISTORY, CUMULATIVE);
    expect(check.checked).toBe(true);
    expect(check.disagreements).toEqual([]);
    expect(check.agrees).toBe(true);
  });

  it('counts compressed rows only for cycles, all rows for incomplete attempts', () => {
    const check = historyAgreement(HISTORY, {
      ...CUMULATIVE,
      compressed_cycles_completed: 4,
    });
    expect(check.agrees).toBe(false);
    expect(check.disagreements.join(' ')).toContain('compressed cycles completed');
  });
});
