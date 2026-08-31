/**
 * The recorded-run bundle: shape, validation and honest accessors.
 *
 * The run surface replays ONE completed cohort execution from its own typed
 * artifacts. This module is the only place that decides whether the bundle is
 * usable; every component downstream asks it rather than guessing, so a missing
 * or malformed export renders as an explicit awaiting state and never as zero,
 * empty or success.
 *
 * The bundle is produced at build time from the terminal evidence export and
 * committed. Nothing is fetched at page load, and nothing here is live.
 */

import bundle from '../site/data/run-bundle.json';

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

export interface RunCase {
  case_id: string;
  state: CaseState;
  audit_status?: string;
  epoch_label?: string;
  terminal_at?: string;
  reason_codes?: string[];
  trace_id?: string;
  /** True when this case's full artifact chain travels in `dossiers`. */
  has_dossier?: boolean;
}

export interface HaltedCase {
  case_id: string;
  reason_codes: string[];
  trace_id?: string;
  failure_receipt?: { artifact_id: string; content_hash: string };
  /** Cases that reached a terminal state after this one halted. */
  cohort_continued_after?: number;
  review_tasks_created: number;
}

export interface RunBundle {
  schema_version: string;
  status: 'PENDING' | 'READY';
  note: string;
  execution?: {
    job: string;
    generation: number | string;
    execution_id?: string;
    region: string;
    terminal_state: string;
    started_at: string;
    finished_at: string;
    source_commit: string;
    image_digest: string;
  };
  cohort?: {
    total_cases: number;
    distribution: Partial<Record<CaseState, number>>;
    artifacts: { valid: number; invalid: number };
    round_trips?: Record<string, number>;
    role_failures?: Record<string, number>;
    manifest?: { path: string; content_hash: string };
    data_mode_receipt?: { path: string; content_hash: string };
  };
  cases?: RunCase[];
  containment?: {
    halted_cases: HaltedCase[];
    review_tasks_from_halted: number;
  };
  provenance?: {
    export_source: string;
    exported_at: string;
    bundle_sha256?: string;
  };
}

const raw = bundle as unknown as RunBundle;

export interface BundleReading {
  ready: boolean;
  /** Why the bundle is not usable, when it is not. Never silently empty. */
  awaiting: string | null;
  bundle: RunBundle;
}

/**
 * A bundle counts as READY only when it declares itself ready AND carries the
 * parts the surface renders. A partial export is an awaiting state with a
 * reason, not a half-drawn screen.
 */
export function readBundle(): BundleReading {
  if (raw.status !== 'READY') {
    return { ready: false, awaiting: raw.note, bundle: raw };
  }
  const missing: string[] = [];
  if (!raw.execution) missing.push('execution binding');
  if (!raw.cohort) missing.push('cohort totals');
  if (!raw.cases || raw.cases.length === 0) missing.push('per-case index');
  if (raw.cohort && raw.cases && raw.cases.length !== raw.cohort.total_cases) {
    missing.push(
      `case index holds ${raw.cases.length} rows for a cohort of ${raw.cohort.total_cases}`,
    );
  }
  if (missing.length > 0) {
    return {
      ready: false,
      awaiting: `The export is incomplete: ${missing.join('; ')}.`,
      bundle: raw,
    };
  }
  return { ready: true, awaiting: null, bundle: raw };
}

/** Counts recomputed from the case index, never read from a summary field. */
export function distributionFromCases(cases: readonly RunCase[]): Record<CaseState, number> {
  const counts = Object.fromEntries(CASE_STATES.map((s) => [s, 0])) as Record<CaseState, number>;
  for (const row of cases) {
    if (row.state in counts) {
      counts[row.state] += 1;
    }
  }
  return counts;
}

/**
 * The declared distribution and the one recomputed from the rows must agree.
 * A disagreement is surfaced, not reconciled: it would mean the summary and
 * the evidence disagree, which the reader is entitled to know.
 */
export function distributionAgrees(bundleValue: RunBundle): boolean {
  if (!bundleValue.cohort || !bundleValue.cases) {
    return false;
  }
  const derived = distributionFromCases(bundleValue.cases);
  return CASE_STATES.every(
    (state) => (bundleValue.cohort!.distribution[state] ?? 0) === derived[state],
  );
}
