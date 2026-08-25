/**
 * Cohort day derivations.
 *
 * Counters are read from the manifest, never accumulated here. What IS derived
 * here is the claim no counter can support: that four days of cohort operation
 * happened. Four runs look identical whether they took four days or one
 * evening, so the sentence is spoken only when the record proves it.
 *
 * Two different things can masquerade as that proof, and both are guarded.
 * Several runs in one evening produce four totals and one date. A job whose
 * selection is pinned to a constant date produces four dates while every run it
 * creates still belongs to the first day: perfect timestamps, false sentence.
 * The subject of the claim is cohort DAYS, not job wakeups, so each day must
 * show it selected work for the day it ran and that the selection produced
 * something.
 *
 * This module refuses upward: every uncertainty resolves to the claim that
 * says less.
 */

export interface CohortExecution {
  day_index?: unknown;
  executed_at?: unknown;
  /** The date the day's case selection was driven by. */
  selected_for_date?: unknown;
  /** Runs this day actually created. */
  runs_created?: unknown;
  /** Runs this day pre-committed to creating, before it ran. */
  runs_predicted?: unknown;
}

export interface CohortCase {
  case_id?: unknown;
  data_mode?: unknown;
  vcv?: unknown;
}

export interface VcvAnchor {
  vcv?: unknown;
  capture_path?: unknown;
  sha256?: unknown;
}

export interface OperationSpan {
  /** Number of execution records present. */
  cycles: number;
  /** Distinct UTC calendar dates among them. */
  distinctDays: number;
  /** Day order and time order agree, strictly increasing. */
  ordered: boolean;
  /** Whether the record proves distinct elapsed days. */
  proven: boolean;
  /** Why the strong claim was withheld, when it was. */
  withheldBecause: string | null;
  sentence: string;
}

/** UTC calendar date of an ISO timestamp, or null when it does not parse. */
function utcDate(value: unknown): string | null {
  if (typeof value !== 'string') {
    return null;
  }
  const ms = Date.parse(value);
  if (Number.isNaN(ms)) {
    return null;
  }
  return new Date(ms).toISOString().slice(0, 10);
}

function plural(count: number, word: string): string {
  return `${count} ${word}${count === 1 ? '' : 's'}`;
}

/**
 * Decide what the execution history is entitled to claim.
 *
 * The claim is about COHORT DAYS, not about a job waking up, and those are not
 * the same thing. Selection pinned to a constant date would execute on four
 * dates while every run it created still belonged to the first: the timestamps
 * would look perfect and the sentence would still be false. So each day must
 * also show that it selected work FOR the day it ran, and that the selection
 * produced runs or pre-committed to producing none.
 *
 * The strong claim requires all of: at least two records; every timestamp
 * parseable; one record per distinct calendar date; day order matching time
 * order; each day's selection date equal to the date it executed; and each day
 * either creating runs or having predicted zero before it ran. Anything less
 * falls back to counting cycles, which stays true however they ran.
 */
export function operationSpan(executions: readonly CohortExecution[]): OperationSpan {
  const cycles = executions.length;
  const weak = (withheldBecause: string | null): OperationSpan => ({
    cycles,
    distinctDays: 0,
    ordered: false,
    proven: false,
    withheldBecause,
    sentence: `${plural(cycles, 'daily cycle')} recorded.`,
  });

  if (cycles === 0) {
    return weak('no execution record');
  }

  const stamps = executions.map((entry) => Date.parse(String(entry.executed_at)));
  const dates = executions.map((entry) => utcDate(entry.executed_at));
  if (dates.some((date) => date === null)) {
    return weak('an execution timestamp did not parse');
  }

  const distinctDays = new Set(dates).size;
  if (distinctDays !== cycles) {
    return {
      ...weak('two runs share a calendar date'),
      distinctDays,
    };
  }

  const byDay = [...executions].map((entry, index) => ({
    day: Number(entry.day_index),
    at: stamps[index],
  }));
  if (byDay.some((entry) => !Number.isFinite(entry.day))) {
    return { ...weak('an execution carried no day index'), distinctDays };
  }
  byDay.sort((left, right) => left.day - right.day);
  const ordered = byDay.every((entry, index) => index === 0 || entry.at > byDay[index - 1].at);
  if (!ordered) {
    return { ...weak('day order and execution order disagree'), distinctDays };
  }

  // A day that selected work for a date other than the one it ran on did not
  // advance the cohort, whatever its timestamp says. This is the exact shape a
  // date-pinned selection leaves behind: execution dates advance, selection
  // date does not.
  const pinned = executions.find((entry, index) => {
    const declared = entry.selected_for_date;
    return typeof declared !== 'string' || declared !== dates[index];
  });
  if (pinned !== undefined) {
    return {
      ...weak(
        typeof pinned.selected_for_date === 'string'
          ? 'a day selected work for a different date than it ran'
          : 'a day did not declare the date its selection was driven by',
      ),
      distinctDays,
      ordered: true,
    };
  }

  // A day that woke up and selected nothing is a job running, not a cohort day.
  // Zero counts only when zero was pre-committed before the day ran.
  const barren = executions.find((entry) => {
    const created = Number(entry.runs_created);
    if (!Number.isFinite(created) || created < 0) {
      return true;
    }
    return created === 0 && Number(entry.runs_predicted) !== 0;
  });
  if (barren !== undefined) {
    return {
      ...weak(
        Number.isFinite(Number(barren.runs_created))
          ? 'a day created no runs and none were predicted'
          : 'a day recorded no selection evidence',
      ),
      distinctDays,
      ordered: true,
    };
  }

  if (cycles < 2) {
    return { ...weak('a single day cannot establish a span'), distinctDays, ordered: true };
  }

  return {
    cycles,
    distinctDays,
    ordered: true,
    proven: true,
    withheldBecause: null,
    sentence: `Day ${cycles} of operation, across ${plural(distinctDays, 'distinct day')}.`,
  };
}

/**
 * What a case's declared data mode means, in words a first-time viewer can use.
 *
 * Recall watches institutional records, not people. No copy here calls a case a
 * patient, and an anchored case says what it is anchored to rather than
 * implying the record itself is real clinical data.
 */
export function caseModeCopy(dataMode: unknown): { plain: string; anchored: boolean } {
  switch (dataMode) {
    case 'SYNTHETIC_WITH_CAPTURED_REPLAY':
      return {
        plain: 'Synthetic record anchored to a captured public evidence file.',
        anchored: true,
      };
    case 'CAPTURED_REPLAY':
      return { plain: 'Replayed from a captured public evidence file.', anchored: true };
    case 'SYNTHETIC':
      return { plain: 'Synthetic record, not anchored to any captured file.', anchored: false };
    case 'MOCK':
      return { plain: 'Fixture record, not anchored to any captured file.', anchored: false };
    default:
      return { plain: 'Data mode not declared by the manifest.', anchored: false };
  }
}

/** The capture file and hash a VCV is anchored to, or null when unanchored. */
export function anchorFor(vcv: unknown, anchors: readonly VcvAnchor[]): VcvAnchor | null {
  if (typeof vcv !== 'string' || vcv.length === 0) {
    return null;
  }
  return anchors.find((anchor) => anchor.vcv === vcv) ?? null;
}

/**
 * A case that names a VCV must be traceable to its capture in one step.
 *
 * A real accession number shown without its chain is the failure the historical
 * replay finding named, so an unmatched VCV is reported as unanchored rather
 * than shown bare.
 */
export function unanchoredVcvs(
  cases: readonly CohortCase[],
  anchors: readonly VcvAnchor[],
): string[] {
  return cases
    .filter((entry) => typeof entry.vcv === 'string' && entry.vcv.length > 0)
    .filter((entry) => anchorFor(entry.vcv, anchors) === null)
    .map((entry) => String(entry.vcv));
}
