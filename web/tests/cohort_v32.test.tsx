/**
 * 3.1/3.2 surfaces: epoch labels, parity, the three-valued audit story.
 *
 * Lane-authored shapes per the shipped parsers at core 375f116 (no producer
 * example exists); pinned values (FULL_AUDIT_V1, IN_PROCESS_ADK_CLOUD_RUN,
 * PLAN5_ prefix) are copied from the contract's own constants.
 */

import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';

import { CohortPanel } from '../src/components/CohortPanel';
import { operationSpan } from '../src/viewmodel/cohort';
import { buildViewModel } from '../src/viewmodel/builder';
import type { ArtifactBundle } from '../src/viewmodel/types';
import example from './fixtures/cohort-day2-manifest.example.json';

function v32Manifest(overrides: Record<string, unknown> = {}) {
  return {
    ...example,
    schema_version: '3.2.0',
    epoch_label: 'PLAN5_R1',
    evaluation_role: 'RAMP_FIRST_PASS',
    ramp_gate_receipt_id: '33333333-3333-5333-8333-333333333333',
    write_metrics: { completed_at: '2026-08-27T12:30:00Z', selected_case_count: 20 },
    parity: {
      expected_newly_created_runs: 20,
      actual_newly_created_runs: 20,
      expected_reused_runs: 0,
      actual_reused_runs: 0,
      parity_match: true,
    },
    agent_execution_summary: {
      execution_profile: 'FULL_AUDIT_V1',
      runtime_class: 'IN_PROCESS_ADK_CLOUD_RUN',
      concurrency: 2,
      model_id: 'gemini-3.7-flash',
      endpoint_class: 'VERTEX_AI_GLOBAL',
      total_runs: 20,
      complete_runs: 17,
      incomplete_runs: 2,
      not_evaluated_runs: 1,
      halted_runs: 0,
      total_agent_invocations: 60,
      total_prompt_tokens: 1000,
      total_candidate_tokens: 400,
      total_thoughts_tokens: 100,
      total_tokens: 1500,
      p50_latency_ms: 900,
      p95_latency_ms: 2100,
      http_429_count: 0,
      projected_cost_usd_micros: 100,
      reserved_cost_usd_micros: 200,
      pricing_policy_sha256: 'b'.repeat(64),
      actual_billed_cost_state: 'NOT_VERIFIED',
    },
    run_outcomes: [
      {
        case_id: '00000000-0000-5000-8000-000000000201',
        run_id: '00000000-0000-5000-8000-000000000301',
        epoch_label: 'PLAN5_R1',
        terminal_state: 'REVIEW_REQUIRED',
        audit_status: 'COMPLETE',
      },
      {
        case_id: '00000000-0000-5000-8000-000000000202',
        run_id: '00000000-0000-5000-8000-000000000302',
        epoch_label: 'PLAN5_R1',
        terminal_state: 'ABSTAIN',
        audit_status: 'NOT_EVALUATED',
      },
    ],
    ...overrides,
  };
}

function build(artifacts: unknown[]) {
  return buildViewModel({
    bundle_id: 'v32',
    bundle_kind: 'DEMO',
    bundle_version: '1.0.0',
    provenance: {},
    artifacts,
  } as unknown as ArtifactBundle);
}

describe('3.1/3.2 acceptance and fields', () => {
  it('accepts 3.1.0 and 3.2.0 beside the earlier versions', () => {
    for (const version of ['3.1.0', '3.2.0']) {
      expect(build([v32Manifest({ schema_version: version })]).rejected, version).toEqual([]);
    }
  });

  it('resolves epoch, role, parity and the agent summary', () => {
    const { fields } = build([v32Manifest()]);
    expect(fields['UI-COHORT-EPOCH-LABEL'].value).toBe('PLAN5_R1');
    expect(fields['UI-COHORT-EVALUATION-ROLE'].value).toBe('RAMP_FIRST_PASS');
    expect(fields['UI-COHORT-PARITY'].value).toBe('true');
    expect(fields['UI-COHORT-AGENT-SUMMARY'].value).toBe(20);
    expect(fields['UI-COHORT-RUN-OUTCOMES'].items).toHaveLength(2);
  });

  it('hides every 3.1/3.2 field on an older manifest instead of guessing', () => {
    const { fields } = build([example]);
    for (const id of [
      'UI-COHORT-EPOCH-LABEL',
      'UI-COHORT-PARITY',
      'UI-COHORT-AGENT-SUMMARY',
      'UI-COHORT-RUN-OUTCOMES',
    ]) {
      expect(fields[id].status, id).toBe('UNKNOWN');
      expect(fields[id].hidden, id).toBe(true);
    }
  });
});

describe('3.2 rendering', () => {
  function render(artifacts: unknown[]): string {
    return renderToStaticMarkup(<CohortPanel model={build(artifacts).fields} />);
  }

  it('shows the epoch label so re-runs never read as different cases', () => {
    const markup = render([v32Manifest()]);
    expect(markup).toContain('PLAN5_R1');
    expect(markup).toContain('data-field-id="UI-COHORT-EPOCH-LABEL"');
    expect(markup).toContain('RAMP_FIRST_PASS');
  });

  it('renders each run outcome with its own three-valued audit status', () => {
    const markup = render([v32Manifest()]);
    expect(markup).toContain('data-audit-status="COMPLETE"');
    expect(markup).toContain('data-audit-status="NOT_EVALUATED"');
    expect(markup).toContain('audit NOT_EVALUATED');
    // Every outcome row carries its epoch, the owner's which-number rule.
    expect(markup.match(/PLAN5_R1/g)!.length).toBeGreaterThanOrEqual(3);
  });

  it('shows parity beside the totals, never folded into them', () => {
    const markup = render([v32Manifest()]);
    expect(markup).toContain('data-field-id="UI-COHORT-PARITY"');
    expect(markup).toContain('reused runs are never counted');
  });
});

describe('3.3.0 declared deadline', () => {
  const DEADLINE_POLICY = {
    trigger_started_at: '2026-08-27T20:00:00Z',
    trigger_window_end: '2026-08-27T20:30:00Z',
    write_timeout_seconds: 300,
    write_deadline: '2026-08-27T21:00:00Z',
    write_completed_at: '2026-08-27T20:40:00Z',
    agent_timeout_seconds: 600,
    agent_deadline: '2026-08-27T22:00:00Z',
    agent_completed_at: '2026-08-27T21:50:00Z',
    execution_timeout_seconds: 3600,
    authoritative_end_to_end_deadline: '2026-08-27T23:00:00Z',
  };

  it('accepts 3.3.0 and resolves the declared boundary', () => {
    const { fields, rejected } = build([
      v32Manifest({ schema_version: '3.3.0', deadline_policy: DEADLINE_POLICY }),
    ]);
    expect(rejected).toEqual([]);
    expect(fields['UI-COHORT-DEADLINE-POLICY'].value).toBe('2026-08-27T23:00:00Z');
  });

  it('judges lateness against the DECLARED boundary, not the inferred window', () => {
    // A cycle past its own window_end but inside the declared deadline: with
    // the declaration the span holds; without it, the window stays
    // authoritative and the same history withholds.
    const lateRow = {
      sequence_index: 3,
      source_schema_version: 'CohortDayManifest/3.0.0',
      cycle_id: 'c1',
      cycle_index: 1,
      cohort_due_date: '2026-08-27',
      scheduled_for: '2026-08-27T20:00:00Z',
      window_start: '2026-08-27T20:00:00Z',
      window_end: '2026-08-27T21:00:00Z',
      trigger_code: 'COHORT_COMPRESSED_MACHINE_TRIGGERED',
      executed_at: '2026-08-27T22:30:00Z',
      runs_created: 2,
      runs_predicted: 2,
      execution_status: 'COMPLETE',
      failure_receipt_id: null,
      evidence_state: 'LIVE_INFRASTRUCTURE_SYNTHETIC_DATA',
      schedule_mode: 'COMPRESSED_MACHINE_TRIGGERED',
    };
    const history = [...example.execution_history, lateRow];

    const withDeclaration = operationSpan(history, {
      endToEndDeadline: '2026-08-27T23:00:00Z',
    });
    expect(withDeclaration.proven).toBe(true);

    const withoutDeclaration = operationSpan(history);
    expect(withoutDeclaration.proven).toBe(false);
    expect(withoutDeclaration.withheldBecause).toBe(
      'a compressed cycle ran outside its declared window',
    );

    const pastEverything = operationSpan(
      [...example.execution_history, { ...lateRow, executed_at: '2026-08-27T23:30:00Z' }],
      { endToEndDeadline: '2026-08-27T23:00:00Z' },
    );
    expect(pastEverything.proven).toBe(false);
    expect(pastEverything.withheldBecause).toBe(
      'a compressed cycle ran past the declared end-to-end deadline',
    );
  });
});

describe('adversarial regressions, closed', () => {
  it('(d) an earlier declaration TIGHTENS the window; late-but-in-window withholds', () => {
    // Run finishes inside its own window but past the declared deadline: the
    // Math.max regression read this as on time; the declaration is the
    // boundary in both directions.
    const row = {
      sequence_index: 3,
      source_schema_version: 'CohortDayManifest/3.0.0',
      cycle_id: 'c1',
      cycle_index: 1,
      cohort_due_date: '2026-08-27',
      scheduled_for: '2026-08-27T20:00:00Z',
      window_start: '2026-08-27T20:00:00Z',
      window_end: '2026-08-27T23:00:00Z',
      trigger_code: 'COHORT_COMPRESSED_MACHINE_TRIGGERED',
      executed_at: '2026-08-27T22:30:00Z',
      runs_created: 2,
      runs_predicted: 2,
      execution_status: 'COMPLETE',
      failure_receipt_id: null,
      evidence_state: 'LIVE_INFRASTRUCTURE_SYNTHETIC_DATA',
      schedule_mode: 'COMPRESSED_MACHINE_TRIGGERED',
    };
    const span = operationSpan([...example.execution_history, row], {
      endToEndDeadline: '2026-08-27T21:00:00Z',
    });
    expect(span.proven).toBe(false);
    expect(span.withheldBecause).toBe(
      'a compressed cycle ran past the declared end-to-end deadline',
    );
  });

  const VALID_POLICY = {
    trigger_started_at: '2026-08-27T20:00:00Z',
    trigger_window_end: '2026-08-27T20:30:00Z',
    write_timeout_seconds: 300,
    write_deadline: '2026-08-27T21:00:00Z',
    write_completed_at: '2026-08-27T20:40:00Z',
    agent_timeout_seconds: 600,
    agent_deadline: '2026-08-27T22:00:00Z',
    agent_completed_at: '2026-08-27T21:50:00Z',
    execution_timeout_seconds: 3600,
    authoritative_end_to_end_deadline: '2026-08-27T23:00:00Z',
  };

  it('(e) malformed deadline blocks become INCOMPLETE, never KNOWN', () => {
    const missingField = { ...VALID_POLICY } as Record<string, unknown>;
    delete missingField.write_deadline;
    const extraField = { ...VALID_POLICY, surprise: 1 };
    const badType = { ...VALID_POLICY, agent_timeout_seconds: 'soon' };
    const badChronology = {
      ...VALID_POLICY,
      authoritative_end_to_end_deadline: '2026-08-27T20:00:00Z',
    };
    const notUtc = { ...VALID_POLICY, write_deadline: '2026-08-27T21:00:00' };
    for (const [label, policy] of Object.entries({
      missingField,
      extraField,
      badType,
      badChronology,
      notUtc,
    })) {
      const { fields } = build([
        v32Manifest({ schema_version: '3.3.0', deadline_policy: policy }),
      ]);
      expect(fields['UI-COHORT-DEADLINE-POLICY'].status, label).toBe('INCOMPLETE');
      expect(fields['UI-COHORT-DEADLINE-POLICY'].value, label).toBeNull();
    }
    // And the valid block still resolves.
    const { fields } = build([
      v32Manifest({ schema_version: '3.3.0', deadline_policy: VALID_POLICY }),
    ]);
    expect(fields['UI-COHORT-DEADLINE-POLICY'].status).toBe('KNOWN');
  });
});
