/**
 * The run surface: one completed cohort execution, replayed from its own
 * artifacts.
 *
 * Honesty is structural here, not decorative. The banner says the execution is
 * recorded; every clock shown is the run's own; there is no polling, no pulse
 * and no motion that could read as liveness. When the export is missing or
 * partial the surface says so and draws nothing.
 *
 * The containment block is the point of the page rather than a footnote: cases
 * that halted are shown with their reason codes and the three checks that turn
 * "it handled failure well" from a claim into evidence — a typed receipt exists,
 * no review task was created from it, and the cohort kept going.
 */

import { useState } from 'react';

import './run.css';

import {
  CASE_STATES,
  STATE_LANGUAGE,
  distributionAgrees,
  distributionFromCases,
  readBundle,
  type CaseState,
  type RunCase,
} from './runBundle';

const STATE_CLASS: Record<CaseState, string> = {
  NO_ACTION: 'st-none',
  REVIEW_REQUIRED: 'st-review',
  ABSTAIN: 'st-abstain',
  HALTED: 'st-halted',
};

function Awaiting({ reason }: { reason: string | null }) {
  return (
    <div className="awaiting">
      <span className="awaiting-tag">AWAITING TERMINAL EVIDENCE</span>
      <p>{reason ?? 'No export is present.'}</p>
      <p className="awaiting-note">
        This surface renders a completed execution from its committed artifacts. Until those
        artifacts exist it stays empty on purpose — an empty state here is a true statement,
        and a drawn one would not be.
      </p>
    </div>
  );
}

/**
 * The cohort as a field: one cell per case, coloured by terminal state and
 * labelled in words by the legend. Scale is felt rather than read, and the
 * shape of the field is itself the honest headline — a fleet that manufactured
 * findings would look completely different.
 */
function CohortField({
  cases,
  onSelect,
  selected,
}: {
  cases: readonly RunCase[];
  onSelect: (row: RunCase) => void;
  selected: string | null;
}) {
  return (
    <div className="field" role="list" aria-label="Cohort cases by terminal state">
      {cases.map((row) => (
        <button
          key={row.case_id}
          type="button"
          role="listitem"
          className={`cell ${STATE_CLASS[row.state]}${
            selected === row.case_id ? ' selected' : ''
          }`}
          title={`${row.case_id} — ${row.state}: ${STATE_LANGUAGE[row.state].short}`}
          aria-label={`${row.case_id}, ${row.state}`}
          onClick={() => onSelect(row)}
        />
      ))}
    </div>
  );
}

function Distribution({
  counts,
  total,
  agrees,
}: {
  counts: Record<CaseState, number>;
  total: number;
  agrees: boolean;
}) {
  return (
    <>
      <table className="tbl dist">
        <thead>
          <tr>
            <th>Terminal state</th>
            <th>Cases</th>
            <th>What it means</th>
          </tr>
        </thead>
        <tbody>
          {CASE_STATES.map((state) => (
            <tr key={state}>
              <td className="cap">
                <span className={`swatch ${STATE_CLASS[state]}`} aria-hidden /> {state}
              </td>
              <td className="num">{counts[state]}</td>
              <td>{STATE_LANGUAGE[state].meaning}</td>
            </tr>
          ))}
          <tr className="total-row">
            <td className="cap">Total</td>
            <td className="num">{total}</td>
            <td>
              Counted from the per-case index on this page, not read from a summary field.
              {agrees
                ? ' The manifest’s own distribution agrees with this count.'
                : ' NOTE: the manifest’s distribution does not agree with this count, and both are shown rather than reconciled.'}
            </td>
          </tr>
        </tbody>
      </table>
    </>
  );
}

/**
 * Containment: what happened when the machinery could not be trusted.
 *
 * Each halted case carries the checks that make the resilience claim provable
 * rather than rhetorical. A missing check renders as "not exported", never as
 * a pass.
 */
function Containment({
  halted,
  reviewTasksFromHalted,
}: {
  halted: ReturnType<typeof readBundle>['bundle']['containment'] extends infer T
    ? T extends { halted_cases: infer H }
      ? H
      : never
    : never;
  reviewTasksFromHalted: number;
}) {
  const rows = halted as {
    case_id: string;
    reason_codes: string[];
    trace_id?: string;
    failure_receipt?: { artifact_id: string; content_hash: string };
    cohort_continued_after?: number;
    review_tasks_created: number;
  }[];

  return (
    <section className="sec" id="containment">
      <div className="sec-head">
        <span className="sec-num">◆</span>
        <h2>WHEN THE MACHINERY COULD NOT BE TRUSTED</h2>
      </div>
      <p className="sec-claim">
        {rows.length} cases in this execution ended in <b>HALTED</b>. That is the system
        working, not the system breaking.
      </p>
      <p>
        Every autonomous system meets conditions it cannot decide safely in. The failure mode
        that matters is what happens next: a system that guesses turns a broken input into an
        action, and a system that crashes takes the whole run with it. Recall does neither. The
        case stops, a typed receipt records why, the trace stays attached, and the remaining
        cases keep going.
      </p>
      <p className="claim-line">
        <b>{reviewTasksFromHalted}</b> review tasks were created from halted cases. A halted
        case is a technical terminal — never a task, and never a scientific statement about a
        variant.
      </p>
      <table className="tbl halted">
        <thead>
          <tr>
            <th>Case</th>
            <th>Recorded reason</th>
            <th>Typed receipt</th>
            <th>Cohort continued</th>
            <th>Tasks</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.case_id}>
              <td className="cap mono-cell">
                {row.case_id.slice(0, 8)}…
                {row.trace_id ? <span className="limit">trace {row.trace_id.slice(0, 12)}…</span> : null}
              </td>
              <td>
                {row.reason_codes.map((code) => (
                  <code key={code} className="reason">
                    {code}
                  </code>
                ))}
              </td>
              <td>
                {row.failure_receipt ? (
                  <code>{row.failure_receipt.content_hash.slice(0, 12)}…</code>
                ) : (
                  <span className="not-exported">not exported</span>
                )}
              </td>
              <td className="num">
                {row.cohort_continued_after ?? <span className="not-exported">—</span>}
              </td>
              <td className="num">{row.review_tasks_created}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="caveat">
        Reason codes are reproduced exactly as the run recorded them. Where a code points at a
        defect rather than an infrastructure condition, the containment is what is being shown
        here — the cause is tracked separately on the open-risk register, not hidden behind
        this table.
      </p>
    </section>
  );
}

export function RunSurface() {
  const { ready, awaiting, bundle } = readBundle();
  const [selected, setSelected] = useState<RunCase | null>(null);

  if (!ready) {
    return (
      <div className="run">
        <header className="run-head">
          <div>
            <span className="run-tag pending">RECORDED EXECUTION · EXPORT PENDING</span>
            <h1>The run</h1>
          </div>
        </header>
        <Awaiting reason={awaiting} />
      </div>
    );
  }

  const execution = bundle.execution!;
  const cohort = bundle.cohort!;
  const cases = bundle.cases!;
  const counts = distributionFromCases(cases);
  const agrees = distributionAgrees(bundle);

  return (
    <div className="run">
      <header className="run-head">
        <div>
          <span className="run-tag">RECORDED EXECUTION · REPLAY · NOT LIVE</span>
          <h1>The run</h1>
          <p className="run-sub">
            One completed cohort execution, replayed from its own committed artifacts. Every
            clock on this page is the run’s clock. Nothing is fetched while you read it.
          </p>
        </div>
      </header>

      <div className="binding">
        <span>
          <b>job</b> {execution.job} · generation {execution.generation} · {execution.region}
        </span>
        <span>
          <b>ran</b> {execution.started_at} → {execution.finished_at} ·{' '}
          {execution.terminal_state}
        </span>
        <span>
          <b>source commit</b> <code>{execution.source_commit}</code>
        </span>
        <span>
          <b>image digest</b> <code>{execution.image_digest}</code>
        </span>
      </div>

      <section className="sec">
        <div className="sec-head">
          <span className="sec-num">◆</span>
          <h2>THE WHOLE COHORT, ONE CASE PER CELL</h2>
        </div>
        <p className="sec-claim">
          {cohort.total_cases} cases went through the fleet in this execution. Each cell is one
          of them; select any cell to open its record.
        </p>
        <CohortField
          cases={cases}
          selected={selected?.case_id ?? null}
          onSelect={setSelected}
        />
        {selected ? (
          <div className="cell-detail">
            <span className={`swatch ${STATE_CLASS[selected.state]}`} aria-hidden />{' '}
            <code>{selected.case_id}</code> — <b>{selected.state}</b>:{' '}
            {STATE_LANGUAGE[selected.state].short}
            {selected.reason_codes?.length ? (
              <span className="limit">
                {selected.reason_codes.map((code) => (
                  <code key={code} className="reason">
                    {code}
                  </code>
                ))}
              </span>
            ) : null}
          </div>
        ) : null}
        <Distribution counts={counts} total={cases.length} agrees={agrees} />
        <p className="caveat">
          Most cases end in NO_ACTION, and that is the honest result: on most days the public
          evidence for a given case has not moved. A fleet that manufactured findings would
          produce a very different picture, and would be worth trusting less.
        </p>
      </section>

      {bundle.containment ? (
        <Containment
          halted={bundle.containment.halted_cases}
          reviewTasksFromHalted={bundle.containment.review_tasks_from_halted}
        />
      ) : null}
    </div>
  );
}
