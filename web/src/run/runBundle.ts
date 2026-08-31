/**
 * The recorded-run bundle: the committed generation-27 export, read as one
 * object, with the readiness rules that keep the surface honest.
 *
 * The files under `data/` are verbatim copies of
 * `artifacts/evidence/generation-27-export/`, and a test holds them to that
 * export's own SHA256SUMS so a copy can never drift from the evidence it
 * claims to be. Nothing is fetched at page load and nothing here is live: the
 * execution completed, and this is its recording.
 */

import casesFile from './data/cases.json';
import cohortFile from './data/cohort-summary.json';
import executionFile from './data/execution-binding.json';
import haltedFile from './data/halted.json';
import manifestFile from './data/manifest.json';
import modeFile from './data/mode-summary.json';

export type CaseState = 'NO_ACTION' | 'REVIEW_REQUIRED' | 'ABSTAIN' | 'HALTED';

export const CASE_STATES: readonly CaseState[] = [
  'NO_ACTION',
  'REVIEW_REQUIRED',
  'ABSTAIN',
  'HALTED',
];

/** Plain-language reading of each terminal state, for a non-specialist. */
export const STATE_LANGUAGE: Record<CaseState, { short: string; meaning: string }> = {
  NO_ACTION: {
    short: 'Nothing to raise',
    meaning:
      'The scan found no audited change that would justify a specialist’s time. The case stays open and is scanned again.',
  },
  REVIEW_REQUIRED: {
    short: 'Sent to a specialist',
    meaning:
      'A material change was complete, independently audited and conflict-free, so exactly one simulated review task was created.',
  },
  ABSTAIN: {
    short: 'Refused to decide',
    meaning:
      'Recall stopped because required proof was incomplete: a needed fact was missing, invalid, failed or conflicted. No task.',
  },
  HALTED: {
    short: 'Refused to run',
    meaning:
      'A technical terminal. The machinery needed to decide safely was not trustworthy for this case, so the case was stopped and recorded instead of guessed. Never a task, and never a scientific statement.',
  },
};

export const ROLES = ['EVIDENCE_WATCHER', 'EVIDENCE_ASSESSOR', 'CITATION_AUDITOR'] as const;
export type Role = (typeof ROLES)[number];

export interface RunCase {
  case: string | null;
  run: string;
  state: CaseState;
  roles: Record<string, string>;
  policy_outcome: string | null;
  policy_reason_codes: string[];
  audit_status: string | null;
  receipts: {
    scan_run: boolean;
    privacy_receipt_hash: string | null;
    policy_decision_hash: string | null;
    citation_audit_hash: string | null;
    data_mode_receipt_hash: string | null;
    failure_receipt_count: number;
  };
  artifact_count: number;
}

export interface HaltedCase {
  case: string;
  run: string;
  failed_role: string | null;
  trace: string | null;
  agent_execution_receipt: {
    technical_code: string | null;
    status: string | null;
    execution_status: string | null;
    content_hash: string | null;
    attempt: number | null;
    latency_ms: number | null;
    turn_count: number;
    finish_reasons: string[];
    http_429_count: number | null;
  };
  failure_receipt: {
    controller_code: string | null;
    stage: string | null;
    safe_terminal: string | null;
    retryable: boolean | null;
    operator_action: string | null;
    budget_state: string | null;
    status: string | null;
    content_hash: string | null;
  };
  closure: {
    policy_decisions: number;
    review_tasks: number;
    terminal_policy_decision_id: string | null;
    artifact_count: number;
  };
}

const cases = casesFile as unknown as { row_count: number; rows: RunCase[] };
const halted = haltedFile as unknown as { halted_count: number; rows: HaltedCase[] };

export const execution = executionFile as unknown as {
  execution_alias: string;
  job: string;
  region: string;
  job_generation: string;
  deployed: Record<string, string>;
  started_at: string;
  completed_at: string;
  duration_seconds: number;
  terminal_state: string;
  succeeded_count: number;
  recovery_prefix_bound: string;
};

export const cohort = cohortFile as unknown as {
  terminal_states: Record<string, number>;
  audit_axis_from_manifest: Record<string, number>;
  artifacts: {
    documents: number;
    parsed_by_production_contract: number;
    parse_failures: number;
    status_field: Record<string, number>;
    schema_mix: Record<string, number>;
  };
  tool_and_gateway: Record<string, number | boolean | Record<string, number>>;
  rate_limiting: { http_429_count: number; cases_failed_by_rate_limiting: number; note: string };
  latency_ms: { p50: number; p95: number };
  tokens: Record<string, number>;
  cost: Record<string, string | number>;
  runtime: Record<string, string | number>;
  review_tasks_in_ledger: number;
  watch_cases_in_ledger: number;
  governance_checks: {
    authorization_decisions: Record<string, number>;
    agent_execution_status_by_role: Record<string, Record<string, number>>;
    distinct_trace_ids: number;
    runs_with_more_than_one_trace: number;
    agent_receipts_without_trace: number;
    tool_calls_without_authorization: number;
    policy_outcomes_seen: Record<string, number>;
    runs_with_started_but_no_terminal_agent_receipt: number;
  };
};

export const manifest = manifestFile as unknown as {
  schema: string;
  status: string;
  content_hash: string;
  epoch_label: string;
  evaluation_role: string;
  data_mode: string;
  agent_execution_summary: Record<string, number | string>;
};

export const modes = modeFile as unknown as {
  run_level_receipts: number;
  cohort_level_receipts: number;
  cohort_level_absent: boolean;
  mode_sets: Record<string, number>;
};

export interface BundleReading {
  ready: boolean;
  /** Why the export is not usable, when it is not. Never silently empty. */
  awaiting: string | null;
  cases: RunCase[];
  halted: HaltedCase[];
}

/**
 * The export counts as usable only when its parts are present and agree with
 * each other. A partial or inconsistent export is an explicit awaiting state
 * with a reason, not a half-drawn screen.
 */
export function readBundle(): BundleReading {
  const missing: string[] = [];
  if (!execution?.started_at || !execution?.completed_at) missing.push('execution binding');
  if (!cases?.rows?.length) missing.push('per-case index');
  if (cases?.rows && cases.row_count !== cases.rows.length) {
    missing.push(
      `the index declares ${cases.row_count} rows and carries ${cases.rows.length}`,
    );
  }
  if (halted?.rows && halted.halted_count !== halted.rows.length) {
    missing.push('the halted count and the halted rows disagree');
  }
  if (missing.length > 0) {
    return {
      ready: false,
      awaiting: `The export is incomplete: ${missing.join('; ')}.`,
      cases: [],
      halted: [],
    };
  }
  return { ready: true, awaiting: null, cases: cases.rows, halted: halted.rows };
}

/** Counts recomputed from the case rows, never read from a summary field. */
export function distributionFromCases(rows: readonly RunCase[]): Record<CaseState, number> {
  const counts = Object.fromEntries(CASE_STATES.map((s) => [s, 0])) as Record<CaseState, number>;
  for (const row of rows) {
    if (row.state in counts) {
      counts[row.state] += 1;
    }
  }
  return counts;
}

/**
 * The declared distribution and the one recomputed from the rows must agree.
 * A disagreement is surfaced, not reconciled.
 */
export function distributionAgrees(rows: readonly RunCase[]): boolean {
  const derived = distributionFromCases(rows);
  return CASE_STATES.every(
    (state) => (cohort.terminal_states[state] ?? 0) === derived[state],
  );
}

/**
 * The role funnel: how many cases each role started, completed and failed.
 * Read from the run's own agent receipts, so every drop between stages is one
 * recorded failure rather than an unexplained gap.
 */
export function roleFunnel(): {
  role: Role;
  started: number;
  completed: number;
  failed: number;
}[] {
  const byRole = cohort.governance_checks.agent_execution_status_by_role;
  return ROLES.map((role) => ({
    role,
    started: byRole[role]?.STARTED ?? 0,
    completed: byRole[role]?.COMPLETED ?? 0,
    failed: byRole[role]?.FAILED ?? 0,
  }));
}
