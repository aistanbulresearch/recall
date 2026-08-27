/**
 * Cohort growth panel.
 *
 * Three things must be true on screen at once. The counters must be the
 * manifest's own figures, not this surface's arithmetic. A mixed cohort must
 * describe itself case by case, because one badge over twelve cases where only
 * some are anchored is a bundle-wide claim standing in for case-level truth.
 * And a real accession number must carry its chain: one step from the VCV to
 * the capture file and hash it came from.
 *
 * The panel hides entirely when no manifest is present. It refuses, visibly,
 * when more than one day's manifest is present, because the view model resolves
 * scalars from the first matching artifact and a stale day would otherwise be
 * displayed with nothing to mark it.
 */

import type { ViewModel } from '../viewmodel/types';
import {
  anchorFor,
  caseModeCopy,
  historyAgreement,
  operationSpan,
  rowStatus,
  scheduleModeCopy,
  unanchoredVcvs,
  type CohortCase,
  type CohortExecution,
  type VcvAnchor,
} from '../viewmodel/cohort';
import { FieldValue } from './FieldValue';

function objectItems<T>(items: ReadonlyArray<unknown>): T[] {
  return items.filter((item): item is T => typeof item === 'object' && item !== null);
}

export function CohortPanel({ model }: { model: ViewModel }) {
  const dayIndex = model['UI-COHORT-DAY-INDEX'];
  const manifestDays = model['UI-COHORT-MANIFEST-DAYS'];

  // No manifest at all: show nothing rather than a frame of empty counters.
  if (dayIndex.status !== 'KNOWN' && manifestDays.status !== 'KNOWN') {
    return null;
  }

  // More than one day's manifest in the bundle. Every scalar below would be
  // taken from whichever happened to be first, so no number here can be
  // attributed to a day and none is shown.
  const manifestCount = manifestDays.status === 'KNOWN' ? manifestDays.items.length : 0;
  if (manifestCount > 1) {
    return (
      <section className="panel panel-cohort" aria-labelledby="cohort-heading">
        <h2 id="cohort-heading">Cohort</h2>
        <p className="panel-empty">
          {manifestCount} day manifests are present in this bundle. A figure here could not be
          attributed to a specific day, so none is shown.
        </p>
      </section>
    );
  }

  const cases = objectItems<CohortCase>(model['UI-COHORT-CASES'].items);
  const anchors = objectItems<VcvAnchor>(model['UI-COHORT-VCV-ANCHORS'].items);
  const executions = objectItems<CohortExecution>(model['UI-COHORT-EXECUTIONS'].items);
  const deadlineField = model['UI-COHORT-DEADLINE-POLICY'];
  const span = operationSpan(executions, {
    endToEndDeadline:
      deadlineField.status === 'KNOWN' && typeof deadlineField.value === 'string'
        ? deadlineField.value
        : undefined,
  });
  const orphans = unanchoredVcvs(cases, anchors);

  // Rebuilt from the fields rather than read as one object, so each number
  // carries its own lineage. Missing entries are skipped by the comparison
  // instead of counting as agreement.
  const numeric = (fieldId: string): number | undefined => {
    const field = model[fieldId];
    return field?.status === 'KNOWN' && typeof field.value === 'number' ? field.value : undefined;
  };
  const agreement = historyAgreement(executions, {
    daily_cycles: numeric('UI-COHORT-CYCLES-TOTAL'),
    compressed_cycles_completed: numeric('UI-COHORT-COMPRESSED-TOTAL'),
    distinct_execution_dates: numeric('UI-COHORT-DISTINCT-DATES'),
    runs_created: numeric('UI-COHORT-RUNS-TOTAL'),
  });

  return (
    <section className="panel panel-cohort" aria-labelledby="cohort-heading">
      <h2 id="cohort-heading">Cohort</h2>

      <p className="panel-copy" data-proven={String(span.proven)}>
        {span.sentence}
        {span.withheldBecause ? (
          <span className="cohort-withheld">
            {' '}
            Elapsed days are not claimed here: {span.withheldBecause}.
          </span>
        ) : null}
      </p>

      {scheduleModeCopy(model['UI-COHORT-SCHEDULE-MODE'].value) ? (
        <p className="cohort-schedule-mode" data-field-id="UI-COHORT-SCHEDULE-MODE">
          {scheduleModeCopy(model['UI-COHORT-SCHEDULE-MODE'].value)}
        </p>
      ) : null}

      {model['UI-COHORT-EPOCH-LABEL'].status === 'KNOWN' ? (
        // Which epoch these numbers measure. A re-evaluated case is the same
        // case in a new epoch, never a different case; the label is what keeps
        // a viewer from misreading run totals as cohort growth.
        <p className="cohort-epoch" data-field-id="UI-COHORT-EPOCH-LABEL">
          Epoch <code>{String(model['UI-COHORT-EPOCH-LABEL'].value)}</code>
          {model['UI-COHORT-EVALUATION-ROLE'].status === 'KNOWN' ? (
            <> · {String(model['UI-COHORT-EVALUATION-ROLE'].value)}</>
          ) : null}
        </p>
      ) : null}

      <div className="field-grid">
        <FieldValue field={model['UI-COHORT-DAY-INDEX']} />
        <FieldValue field={model['UI-COHORT-CYCLE-ID']} />
        <FieldValue
          field={model['UI-COHORT-CASES-DELTA']}
          hint="Read from the day manifest, not counted by this surface."
        />
        <FieldValue field={model['UI-COHORT-RUNS-DELTA']} />
        <FieldValue field={model['UI-COHORT-RUNS-TOTAL']} />
        <FieldValue field={model['UI-COHORT-CYCLES-TOTAL']} />
        <FieldValue field={model['UI-COHORT-COMPRESSED-TOTAL']} />
        <FieldValue
          field={model['UI-COHORT-DEADLINE-POLICY']}
          hint="The declared end-to-end boundary; lateness is judged against this, never inferred."
        />
        <FieldValue
          field={model['UI-COHORT-PARITY']}
          hint="Every run newly created this epoch; reused runs are never counted as today's work."
        />
        <FieldValue
          field={model['UI-COHORT-AGENT-SUMMARY']}
          hint="Total runs; complete, incomplete and not-evaluated are separate counts, never collapsed."
        />
      </div>

      {executions.some((entry) => rowStatus(entry) === 'INCOMPLETE') ? (
        <ul className="cohort-incomplete-days">
          {executions
            .filter((entry) => rowStatus(entry) === 'INCOMPLETE')
            .map((entry) => (
              <li key={String(entry.day_index)}>
                Day {String(entry.day_index)} did not complete. Failure receipt{' '}
                <code>{String(entry.failure_receipt_id ?? 'MISSING')}</code>
              </li>
            ))}
        </ul>
      ) : null}

      {agreement.checked ? (
        <p className="cohort-agreement" data-agrees={String(agreement.agrees)}>
          {agreement.agrees
            ? 'The running totals match the execution history they were derived from.'
            : 'These totals disagree with the manifest’s own history: '}
          {agreement.disagreements.join('; ')}
        </p>
      ) : null}

      <h3>Which code produced this</h3>
      <div className="field-grid">
        <FieldValue
          field={model['UI-COHORT-IMAGE-DIGEST']}
          hint="The running artifact this day's evidence came from."
        />
        <FieldValue
          field={model['UI-COHORT-DATA-MODE']}
          hint="A synthetic manifest carries a sentinel digest, not a deployed one."
        />
        <FieldValue field={model['UI-COHORT-SOURCE-COMMIT']} />
        <FieldValue
          field={model['UI-COHORT-PLAN-SHA256']}
          hint="Pre-committed prediction plan every cycle's counters trace to."
        />
      </div>

      {cases.length > 0 ? (
        <>
          <h3>Cases in this cohort</h3>
          <ul className="cohort-cases">
            {cases.map((entry, index) => {
              const mode = caseModeCopy(entry.data_mode);
              const anchor = anchorFor(entry.vcv, anchors);
              return (
                <li
                  key={String(entry.case_id ?? index)}
                  data-mode={String(entry.data_mode ?? 'UNDECLARED')}
                  data-anchored={String(anchor !== null)}
                >
                  <code className="cohort-case-id">{String(entry.case_id ?? 'UNDECLARED')}</code>
                  <span className="cohort-case-mode">{String(entry.data_mode ?? 'UNDECLARED')}</span>
                  <span className="cohort-case-copy">{mode.plain}</span>
                  {typeof entry.vcv === 'string' && entry.vcv.length > 0 ? (
                    <span className="cohort-case-chain">
                      <code>{entry.vcv}</code>
                      {anchor ? (
                        <>
                          {' → '}
                          <code>{String(anchor.capture_path ?? 'UNDECLARED')}</code>
                          {' '}
                          <code className="cohort-hash">{String(anchor.sha256 ?? 'UNDECLARED')}</code>
                        </>
                      ) : (
                        <span className="cohort-unanchored">
                          {' '}
                          no capture anchor in this manifest
                        </span>
                      )}
                    </span>
                  ) : null}
                </li>
              );
            })}
          </ul>
        </>
      ) : null}

      {model['UI-COHORT-RUN-OUTCOMES'].status === 'KNOWN' &&
      model['UI-COHORT-RUN-OUTCOMES'].items.length > 0 ? (
        <>
          <h3>Run outcomes</h3>
          <ul className="cohort-outcomes">
            {objectItems<Record<string, unknown>>(model['UI-COHORT-RUN-OUTCOMES'].items).map(
              (outcome, index) => (
                <li
                  key={String(outcome.run_id ?? index)}
                  data-audit-status={String(outcome.audit_status ?? 'UNDECLARED')}
                >
                  <code>{String(outcome.case_id ?? 'UNDECLARED').slice(0, 8)}</code>
                  <span className="outcome-state">{String(outcome.terminal_state ?? '?')}</span>
                  <span className="outcome-audit">audit {String(outcome.audit_status ?? '?')}</span>
                  <span className="outcome-epoch">{String(outcome.epoch_label ?? '?')}</span>
                </li>
              ),
            )}
          </ul>
        </>
      ) : null}

      {orphans.length > 0 ? (
        <p className="cohort-warning">
          {orphans.length} accession number{orphans.length === 1 ? '' : 's'} on this panel
          {orphans.length === 1 ? ' has' : ' have'} no capture anchor in the manifest and cannot be
          traced from here.
        </p>
      ) : null}
    </section>
  );
}
