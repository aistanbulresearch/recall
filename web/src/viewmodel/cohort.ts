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
  /** 2.1.0+: COMPLETE or INCOMPLETE. Absent on 2.0.0 rows. */
  execution_status?: unknown;
  /** 2.1.0+: the typed failure receipt an INCOMPLETE day must reference. */
  failure_receipt_id?: unknown;
  /** 3.0.0: declared schedule mode of the row; the compressed declaration. */
  schedule_mode?: unknown;
  /** 3.0.0: which contract governs THIS row; rows validate by their own rules. */
  source_schema_version?: unknown;
  /** 3.0.0: per-row trigger evidence. */
  trigger_code?: unknown;
  /** 3.0.0: the due date the cycle's selection was driven by. */
  cohort_due_date?: unknown;
  /** 3.0.0: cycle window bounds; executed_at must fall inside them. */
  window_start?: unknown;
  window_end?: unknown;
  cycle_id?: unknown;
  sequence_index?: unknown;
}

/** The 3.0.0 compressed-row declaration value, pinned by the contract. */
export const COMPRESSED_SCHEDULE_MODE = 'COMPRESSED_MACHINE_TRIGGERED';

/** Is this row a declared compressed-session cycle? */
export function isCompressedRow(entry: CohortExecution): boolean {
  return entry.schedule_mode === COMPRESSED_SCHEDULE_MODE;
}

/**
 * What the row's declared schedule mode means, in words. The label rides on
 * the artifact field, never on copy typed into a component; an undeclared mode
 * gets no label at all rather than a guessed one.
 */
export function scheduleModeCopy(mode: unknown): string | null {
  if (mode === COMPRESSED_SCHEDULE_MODE) {
    return 'Machine-triggered accelerated schedule (supervised verification)';
  }
  return null;
}

/**
 * A 2.0.0 row carries no execution_status, and under that contract every
 * recorded row WAS a completed execution: executed_at was required and
 * non-null. So the absence of the field is itself evidence of COMPLETE, not an
 * unknown to refuse on. Anything other than the two contract values is treated
 * as INCOMPLETE-shaped and fails the receipt requirement below, so an invented
 * status cannot pass as a completed day.
 */
export function rowStatus(entry: CohortExecution): 'COMPLETE' | 'INCOMPLETE' {
  if (entry.execution_status === undefined || entry.execution_status === 'COMPLETE') {
    return 'COMPLETE';
  }
  return 'INCOMPLETE';
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
 * The strong claim requires all of: at least two COMPLETED days; every
 * completed timestamp parseable; one completed record per distinct calendar
 * date; day order matching time order; each completed day's selection date
 * equal to the date it executed; and each completed day either creating runs
 * or having predicted zero before it ran. A 2.1.0 INCOMPLETE day does not
 * poison the claim: it must carry a typed failure receipt and zero created
 * runs, and it is then counted and named rather than folded into the span.
 * Anything less falls back to counting cycles, which stays true however they
 * ran.
 */
export interface SpanOptions {
  /**
   * 3.3.0: the manifest's declared authoritative end-to-end deadline. When
   * present, a compressed cycle finishing past its own window_end but within
   * this DECLARED boundary is not a withhold: the declaration, not an inferred
   * window, is the timing contract. Absent, window_end stays authoritative.
   */
  endToEndDeadline?: string;
}

export function operationSpan(
  executions: readonly CohortExecution[],
  options: SpanOptions = {},
): OperationSpan {
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

  // 2.1.0 distinguishes a day that ran from a day that failed with a typed
  // receipt. The gates below prove the COMPLETE days; an INCOMPLETE day is not
  // proof of anything by itself, but it is an honest record, so it does not
  // poison the claim the complete days can still carry. It is counted and
  // named, never folded into the span.
  const complete = executions.filter((entry) => rowStatus(entry) === 'COMPLETE');
  const incomplete = executions.filter((entry) => rowStatus(entry) === 'INCOMPLETE');
  // Declared compressed cycles are judged by their own rules: date-sharing
  // among them is the DECLARED design, not evidence of a faked span. An
  // UNDECLARED shared date still withholds below, so the fake-compression
  // guard survives the compression era intact.
  const compressed = complete.filter(isCompressedRow);
  const dayRows = complete.filter((entry) => !isCompressedRow(entry));

  // An incomplete day with no typed receipt is not the 2.1.0 shape; it is a
  // hole. The contract requires the reference, so its absence withholds.
  const unreceipted = incomplete.find(
    (entry) => typeof entry.failure_receipt_id !== 'string' || entry.failure_receipt_id.length === 0,
  );
  if (unreceipted !== undefined) {
    return weak('an incomplete day carries no failure receipt');
  }
  // The contract also pins an incomplete day to zero created runs.
  if (incomplete.some((entry) => Number(entry.runs_created) !== 0)) {
    return weak('an incomplete day claims to have created runs');
  }

  if (complete.length === 0) {
    return weak('no day completed');
  }

  // Gates for the declared compressed rows, mirroring the shipped contract as
  // defence in depth: parseable timestamp inside the declared window, trigger
  // evidence present, and the cycle's runs matching its pre-committed
  // prediction (the contract refuses a mismatched cycle outright).
  for (const row of compressed) {
    const executed = Date.parse(String(row.executed_at));
    if (Number.isNaN(executed)) {
      return weak('a compressed cycle timestamp did not parse');
    }
    const start = Date.parse(String(row.window_start));
    const end = Date.parse(String(row.window_end));
    const declared = options.endToEndDeadline ? Date.parse(options.endToEndDeadline) : NaN;
    // When a valid declaration exists it IS the boundary, in both directions:
    // an earlier declaration tightens the window, a later one extends it.
    // Math.max here would let a run finishing after the declared deadline but
    // before window_end read as on time, which is the opposite of a contract.
    const boundary = Number.isNaN(declared) ? end : declared;
    if (Number.isNaN(start) || Number.isNaN(end) || executed < start || executed > boundary) {
      return weak(
        Number.isNaN(declared)
          ? 'a compressed cycle ran outside its declared window'
          : 'a compressed cycle ran past the declared end-to-end deadline',
      );
    }
    if (typeof row.trigger_code !== 'string' || row.trigger_code.length === 0) {
      return weak('a compressed cycle carries no trigger evidence');
    }
    if (Number(row.runs_created) !== Number(row.runs_predicted)) {
      return weak('a compressed cycle missed its pre-committed prediction');
    }
  }
  const compressedStamps = compressed.map((row) => Date.parse(String(row.executed_at)));
  const compressedOrdered = compressedStamps.every(
    (at, index) => index === 0 || at > compressedStamps[index - 1],
  );
  if (!compressedOrdered) {
    return weak('compressed cycle order and execution order disagree');
  }

  const stamps = dayRows.map((entry) => Date.parse(String(entry.executed_at)));
  const dates = dayRows.map((entry) => utcDate(entry.executed_at));
  if (dates.some((date) => date === null)) {
    return weak('an execution timestamp did not parse');
  }

  const distinctDays = new Set(dates).size;
  if (distinctDays !== dayRows.length) {
    return {
      ...weak('two runs share a calendar date'),
      distinctDays,
    };
  }

  const byDay = [...dayRows].map((entry, index) => ({
    // 2.x rows carry day_index; 3.0.0 history rows order by sequence_index.
    day: Number(entry.day_index ?? entry.sequence_index),
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
  // date does not. The 2.1.0 contract now enforces this equality itself for
  // COMPLETE rows; this stays as defence in depth against a producer that does
  // not run that parser.
  const pinned = dayRows.find((entry, index) => {
    // 2.x rows declare selected_for_date; CohortHistoryReceipt day rows declare
    // cohort_due_date. Either one must equal the date the row executed.
    const declared = entry.selected_for_date ?? entry.cohort_due_date;
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

  // A COMPLETE day that woke up and selected nothing is a job running, not a
  // cohort day. Zero counts only when zero was pre-committed before it ran. An
  // INCOMPLETE day is exempt: its zero is what failure looks like, and the
  // typed receipt already accounts for it.
  const barren = dayRows.find((entry) => {
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

  if (complete.length < 2) {
    return { ...weak('a single completed cycle cannot establish a span'), distinctDays, ordered: true };
  }

  const parts: string[] = [];
  if (dayRows.length > 0) {
    parts.push(`${plural(distinctDays, 'completed day')} on distinct dates`);
  }
  if (compressed.length > 0) {
    parts.push(
      `${plural(compressed.length, 'cycle')} in the declared machine-triggered compressed session`,
    );
  }
  if (incomplete.length > 0) {
    parts.push(`${plural(incomplete.length, 'incomplete attempt')} with a typed failure receipt`);
  }
  const sentence =
    compressed.length === 0 && incomplete.length === 0
      ? `Day ${cycles} of operation, across ${plural(distinctDays, 'distinct day')}.`
      : `${plural(cycles, 'recorded cycle')}: ${parts.join(', ')}.`;

  return {
    cycles,
    distinctDays,
    ordered: true,
    proven: true,
    withheldBecause: null,
    sentence,
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
    // The only two modes the 2.0.0 contract permits for a case. It also enforces
    // that vcv is null exactly when the mode is SYNTHETIC_ONLY, so anchored and
    // unanchored are contract-level facts rather than presentation choices.
    case 'SYNTHETIC_WITH_CAPTURED_REPLAY':
      return {
        plain: 'Synthetic record anchored to a captured public evidence file.',
        anchored: true,
      };
    case 'SYNTHETIC_ONLY':
      return { plain: 'Synthetic record, not anchored to any captured file.', anchored: false };
    default:
      return { plain: 'Data mode not declared by the manifest.', anchored: false };
  }
}

export interface CohortCumulative {
  daily_cycles?: unknown;
  distinct_execution_dates?: unknown;
  runs_created?: unknown;
  runs_predicted?: unknown;
  /** 3.0.0 names. */
  compressed_cycles_completed?: unknown;
  successful_compressed_cycles?: unknown;
  logical_days_covered?: unknown;
  historical_incomplete_attempts?: unknown;
}

export interface HistoryAgreement {
  /** Whether there was enough of both sides to compare at all. */
  checked: boolean;
  agrees: boolean;
  disagreements: string[];
}

/**
 * Does the manifest's own running total agree with the history it was derived
 * from?
 *
 * The producer computes `cumulative` from `execution_history`. This surface
 * derives the same quantities from the same rows, independently. That makes the
 * two comparable, and comparison is worth more than either number alone: a
 * manifest whose totals disagree with its own rows is reporting something no
 * reader can reconcile, and the panel should say so rather than pick a side.
 *
 * This checks agreement WITHIN the manifest. It cannot check that the rows
 * describe what actually ran, which needs evidence this artifact does not carry.
 */
export function historyAgreement(
  executions: readonly CohortExecution[],
  cumulative: CohortCumulative | null,
): HistoryAgreement {
  if (!cumulative || executions.length === 0) {
    return { checked: false, agrees: false, disagreements: [] };
  }

  // Mirrors the producer's own derivation for whichever contract shaped the
  // history. 3.0.0 (any declared compressed row present): cycle and run counts
  // range over COMPRESSED rows only, distinct dates over compressed executed
  // dates, logical days over compressed due dates, and incomplete attempts
  // over ALL rows. 2.1.0: daily_cycles and distinct dates count COMPLETE rows,
  // run sums range over all rows. Deriving anything else here would
  // manufacture a disagreement out of semantics.
  const complete = executions.filter((entry) => rowStatus(entry) === 'COMPLETE');
  const compressed = complete.filter(isCompressedRow);
  const v3 = compressed.length > 0;
  const scope = v3 ? compressed : executions;
  const sum = (key: 'runs_created' | 'runs_predicted') =>
    scope.reduce((total, entry) => total + Number(entry[key] ?? NaN), 0);
  const dates = (v3 ? compressed : complete).map((entry) => utcDate(entry.executed_at));

  const comparisons: Array<[string, unknown, number]> = v3
    ? [
        ['compressed cycles completed', cumulative.compressed_cycles_completed, compressed.length],
        [
          'successful compressed cycles',
          cumulative.successful_compressed_cycles,
          compressed.filter((row) => Number(row.runs_created) === Number(row.runs_predicted)).length,
        ],
        ['distinct execution dates', cumulative.distinct_execution_dates, new Set(dates).size],
        [
          'logical days covered',
          cumulative.logical_days_covered,
          new Set(compressed.map((row) => String(row.cohort_due_date))).size,
        ],
        ['runs created', cumulative.runs_created, sum('runs_created')],
        ['runs predicted', cumulative.runs_predicted, sum('runs_predicted')],
        [
          'historical incomplete attempts',
          cumulative.historical_incomplete_attempts,
          executions.filter((entry) => rowStatus(entry) === 'INCOMPLETE').length,
        ],
      ]
    : [
        ['daily cycles', cumulative.daily_cycles, complete.length],
        ['distinct execution dates', cumulative.distinct_execution_dates, new Set(dates).size],
        ['runs created', cumulative.runs_created, sum('runs_created')],
        ['runs predicted', cumulative.runs_predicted, sum('runs_predicted')],
      ];

  const disagreements: string[] = [];
  let compared = 0;
  for (const [label, declared, derived] of comparisons) {
    if (typeof declared !== 'number' || !Number.isFinite(derived)) {
      continue;
    }
    compared += 1;
    if (declared !== derived) {
      disagreements.push(`${label}: manifest says ${declared}, its own history shows ${derived}`);
    }
  }

  return {
    checked: compared > 0,
    agrees: compared > 0 && disagreements.length === 0,
    disagreements,
  };
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
