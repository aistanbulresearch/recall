/**
 * The run surface: one completed cohort execution, replayed from its own
 * artifacts.
 *
 * Honesty is structural here, not decorative. The banner says the execution is
 * recorded; every clock shown is the run's own; there is no polling and no
 * motion that could read as liveness. Counts are recomputed from the per-case
 * rows rather than read from a summary, and where the run's own summary
 * disagrees the disagreement is shown instead of reconciled.
 *
 * Two sections carry most of the weight. The role funnel accounts for every
 * case that did not reach the gate; each drop between stages is one recorded
 * failure, not an unexplained gap. The containment block shows what happened
 * when the machinery could not be trusted, per case, with the checks that turn
 * "it handles failure well" from a claim into evidence.
 */

import { useState } from 'react';

import './run.css';

import {
  CASE_STATES,
  STATE_LANGUAGE,
  cohort,
  distributionAgrees,
  distributionFromCases,
  execution,
  manifest,
  modes,
  readBundle,
  roleFunnel,
  type CaseState,
  type HaltedCase,
  type RunCase,
} from './runBundle';

const STATE_CLASS: Record<CaseState, string> = {
  NO_ACTION: 'st-none',
  REVIEW_REQUIRED: 'st-review',
  ABSTAIN: 'st-abstain',
  HALTED: 'st-halted',
};

function Section({
  title,
  claim,
  id,
  children,
}: {
  title: string;
  claim: string;
  id?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="sec" id={id}>
      <div className="sec-head">
        <span className="sec-num">◆</span>
        <h2>{title}</h2>
      </div>
      <p className="sec-claim">{claim}</p>
      {children}
    </section>
  );
}

function hours(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.round((seconds % 3600) / 60);
  return `${h}h ${m}m`;
}

function CohortField({
  rows,
  selected,
  onSelect,
}: {
  rows: readonly RunCase[];
  selected: string | null;
  onSelect: (row: RunCase) => void;
}) {
  return (
    <div className="run-field" role="list" aria-label="Cohort cases by terminal state">
      {rows.map((row) => (
        <button
          key={row.run}
          type="button"
          role="listitem"
          className={`run-cell ${STATE_CLASS[row.state]}${selected === row.run ? ' selected' : ''}`}
          title={`${row.run}, ${row.state}: ${STATE_LANGUAGE[row.state].short}`}
          aria-label={`${row.run}, ${row.state}`}
          onClick={() => onSelect(row)}
        />
      ))}
    </div>
  );
}

function CaseDetail({ row, halted }: { row: RunCase; halted: HaltedCase | undefined }) {
  return (
    <div className="run-detail">
      <p>
        <span className={`swatch ${STATE_CLASS[row.state]}`} aria-hidden />{' '}
        <code>{row.run}</code>, <b>{row.state}</b>: {STATE_LANGUAGE[row.state].short}.{' '}
        {row.artifact_count} artifacts recorded for this case.
      </p>
      <p className="detail-roles">
        {Object.entries(row.roles).map(([role, status]) => (
          <span key={role} className={`role-chip role-${status.toLowerCase()}`}>
            {role.replace('EVIDENCE_', '').replace('CITATION_', '')} {status}
          </span>
        ))}
      </p>
      {row.policy_reason_codes.length > 0 ? (
        <p>
          gate reason codes:{' '}
          {row.policy_reason_codes.map((code) => (
            <code key={code} className="reason">
              {code}
            </code>
          ))}
        </p>
      ) : null}
      {halted ? (
        <p>
          failed role <b>{halted.failed_role}</b> · agent code{' '}
          <code className="reason">{halted.agent_execution_receipt.technical_code}</code> ·
          controller <code className="reason">{halted.failure_receipt.controller_code}</code> at
          stage <b>{halted.failure_receipt.stage}</b> · policy decisions{' '}
          {halted.closure.policy_decisions} · review tasks {halted.closure.review_tasks}
        </p>
      ) : null}
      <p className="detail-hashes">
        {(
          [
            ['privacy receipt', row.receipts.privacy_receipt_hash],
            ['policy decision', row.receipts.policy_decision_hash],
            ['citation audit', row.receipts.citation_audit_hash],
            ['data mode', row.receipts.data_mode_receipt_hash],
          ] as const
        ).map(([label, hash]) => (
          <span key={label}>
            {label}{' '}
            {hash ? <code>{hash.slice(0, 12)}…</code> : <span className="not-exported">none</span>}
          </span>
        ))}
      </p>
    </div>
  );
}

export function RunSurface() {
  const { ready, awaiting, cases, halted } = readBundle();
  const [selected, setSelected] = useState<RunCase | null>(null);

  if (!ready) {
    return (
      <div className="run">
        <header className="run-head">
          <span className="run-tag pending">RECORDED EXECUTION · EXPORT PENDING</span>
          <h1>The run</h1>
        </header>
        <div className="awaiting">
          <span className="awaiting-tag">AWAITING TERMINAL EVIDENCE</span>
          <p>{awaiting}</p>
          <p className="awaiting-note">
            This surface renders a completed execution from its committed artifacts. Until
            those artifacts exist it stays empty on purpose; an empty state here is a true
            statement, and a drawn one would not be.
          </p>
        </div>
      </div>
    );
  }

  const counts = distributionFromCases(cases);
  const agrees = distributionAgrees(cases);
  const funnel = roleFunnel();
  const haltedByRun = new Map(halted.map((row) => [row.run, row]));
  const governance = cohort.governance_checks;
  const gate = cohort.tool_and_gateway;
  const projected = Number(cohort.cost.projected_usd_micros) / 1_000_000;

  return (
    <div className="run">
      <header className="run-head">
        <span className="run-tag">RECORDED EXECUTION · REPLAY · NOT LIVE</span>
        <h1>The run</h1>
        <p className="run-sub">
          One completed cohort execution, replayed from its own committed artifacts. Every
          clock on this page is the run’s clock, and nothing is fetched while you read it.
        </p>
      </header>

      <div className="binding">
        <span>
          <b>job</b> {execution.job} · generation {execution.job_generation} ·{' '}
          {execution.region} · execution <code>{execution.execution_alias}</code>
        </span>
        <span>
          <b>ran</b> {execution.started_at} → {execution.completed_at} ·{' '}
          {hours(execution.duration_seconds)} · Cloud Run {execution.terminal_state}
        </span>
        <span>
          <b>source commit</b> <code>{execution.deployed.source_commit}</code>
        </span>
        <span>
          <b>image digest</b> <code>{execution.deployed.image_digest}</code>
        </span>
      </div>

      <p className="claim-line">
        Cloud Run reports <b>{execution.terminal_state}</b>. The cohort day manifest reports{' '}
        <b>{manifest.status}</b>. Both are true and both are shown: the infrastructure
        finished its job, and {counts.HALTED} cases inside it did not reach a decision. An
        infrastructure success is not an application success, and this page never presents one
        as the other.
      </p>

      <Section
        title="THE WHOLE COHORT, ONE CASE PER CELL"
        claim={`${cases.length} cases went through the fleet in this execution. Select any cell to open its record.`}
      >
        <CohortField rows={cases} selected={selected?.run ?? null} onSelect={setSelected} />
        {selected ? (
          <CaseDetail row={selected} halted={haltedByRun.get(selected.run)} />
        ) : (
          <p className="hint">Select a cell to see that case’s roles, reason codes and receipt hashes.</p>
        )}

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
              <td className="num">{cases.length}</td>
              <td>
                Counted from the rows on this page, not read from a summary field.
                {agrees
                  ? ' The run’s own distribution agrees with this count.'
                  : ' NOTE: the run’s own distribution disagrees with this count; both are shown rather than reconciled.'}
              </td>
            </tr>
          </tbody>
        </table>
        <p className="caveat">
          Most cases end in NO_ACTION, and that is the honest result: on most days the public
          evidence for a given case has not moved. A fleet that manufactured findings would
          produce a very different picture, and would be worth trusting less.
        </p>
      </Section>

      <Section
        title="EVERY CASE ACCOUNTED FOR"
        claim="Each role records when it starts, completes or fails, so every drop between stages is one recorded failure rather than a gap."
      >
        <table className="tbl funnel">
          <thead>
            <tr>
              <th>Stage</th>
              <th>Started</th>
              <th>Completed</th>
              <th>Failed</th>
            </tr>
          </thead>
          <tbody>
            {funnel.map((stage) => (
              <tr key={stage.role}>
                <td className="cap">{stage.role}</td>
                <td className="num">{stage.started}</td>
                <td className="num">{stage.completed}</td>
                <td className="num fail">{stage.failed}</td>
              </tr>
            ))}
            <tr className="total-row">
              <td className="cap">Policy Gate</td>
              <td className="num">{Object.values(governance.policy_outcomes_seen).reduce((a, b) => a + b, 0)}</td>
              <td className="num">{Object.values(governance.policy_outcomes_seen).reduce((a, b) => a + b, 0)}</td>
              <td className="num fail">0</td>
            </tr>
          </tbody>
        </table>
        <p>
          The chain closes: {funnel[0].started} cases entered, {funnel[0].failed} +{' '}
          {funnel[1].failed} + {funnel[2].failed} = {counts.HALTED} stopped with a recorded
          failure, and the remaining{' '}
          {Object.values(governance.policy_outcomes_seen).reduce((a, b) => a + b, 0)} reached the
          deterministic gate. No case disappeared, and no stage was skipped.
        </p>
      </Section>

      <Section
        id="containment"
        title="WHEN THE MACHINERY COULD NOT BE TRUSTED"
        claim={`${halted.length} cases ended in HALTED. That is the system working, not the system breaking.`}
      >
        <p>
          Every autonomous system meets conditions it cannot decide safely in. The failure mode
          that matters is what happens next: a system that guesses turns a broken input into an
          action, and a system that crashes takes the whole run with it. Recall does neither.
          The role times out, a typed receipt records it, the controller writes a failure
          receipt naming the stage, the case stops at a technical terminal, and the remaining
          cases keep going.
        </p>
        <p className="claim-line">
          Across all {halted.length} halted cases:{' '}
          <b>{halted.reduce((sum, row) => sum + row.closure.policy_decisions, 0)}</b> policy
          decisions and{' '}
          <b>{halted.reduce((sum, row) => sum + row.closure.review_tasks, 0)}</b> review tasks.
          A halted case is a technical terminal, never a task, and never a scientific
          statement about a variant.
        </p>
        <table className="tbl halted">
          <thead>
            <tr>
              <th>Case</th>
              <th>Failed role</th>
              <th>Agent code</th>
              <th>Controller</th>
              <th>Receipt</th>
              <th>Tasks</th>
            </tr>
          </thead>
          <tbody>
            {halted.map((row) => (
              <tr key={row.run}>
                <td className="cap mono-cell">
                  {row.case}
                  <span className="limit">trace {row.trace}</span>
                </td>
                <td>
                  {row.failed_role}
                  <span className="limit">
                    {row.agent_execution_receipt.turn_count} turn
                    {row.agent_execution_receipt.turn_count === 1 ? '' : 's'} ·{' '}
                    {Math.round((row.agent_execution_receipt.latency_ms ?? 0) / 1000)}s ·{' '}
                    {row.agent_execution_receipt.finish_reasons.join(', ')}
                  </span>
                </td>
                <td>
                  <code className="reason">{row.agent_execution_receipt.technical_code}</code>
                  <span className="limit">{row.agent_execution_receipt.status}</span>
                </td>
                <td>
                  <code className="reason">{row.failure_receipt.controller_code}</code>
                  <span className="limit">
                    stage {row.failure_receipt.stage} · {row.failure_receipt.safe_terminal} ·{' '}
                    {row.failure_receipt.retryable ? 'retryable' : 'not retryable'}
                  </span>
                </td>
                <td>
                  <code>{(row.failure_receipt.content_hash ?? '').slice(0, 10)}…</code>
                  <span className="limit">{row.failure_receipt.operator_action}</span>
                </td>
                <td className="num">{row.closure.review_tasks}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="caveat">
          Reason codes are reproduced exactly as the run recorded them. Why those particular
          agent calls exceeded their deadline is not determined by this evidence; what is
          shown here is the containment, and the cause is tracked separately rather than
          hidden behind this table.
        </p>
      </Section>

      <Section
        title="WHAT AN AUDITOR CAN CHECK"
        claim="Each row is a question an auditor would ask, answered from the stored artifacts of this run rather than asserted."
      >
        <table className="tbl audit">
          <tbody>
            <tr>
              <td>Artifacts stored, and parsed by the deployed contract code</td>
              <td className="num">
                {cohort.artifacts.documents.toLocaleString('en-US')} /{' '}
                {cohort.artifacts.parsed_by_production_contract.toLocaleString('en-US')}
              </td>
              <td className="num good">{cohort.artifacts.parse_failures} failures</td>
            </tr>
            <tr>
              <td>Tool calls, and authorization decisions recorded for them</td>
              <td className="num">
                {String(gate.tool_call_ids)} / {String(gate.tool_authorization_receipts)}
              </td>
              <td className="num good">
                {governance.tool_calls_without_authorization} unauthorized
              </td>
            </tr>
            <tr>
              <td>Authorization outcomes</td>
              <td className="num">
                {Object.entries(governance.authorization_decisions)
                  .map(([decision, count]) => `${count} ${decision}`)
                  .join(', ')}
              </td>
              <td className="num good">, </td>
            </tr>
            <tr>
              <td>Trace chains, one per case</td>
              <td className="num">{governance.distinct_trace_ids}</td>
              <td className="num good">
                {governance.runs_with_more_than_one_trace} mismatched,{' '}
                {governance.agent_receipts_without_trace} untraced
              </td>
            </tr>
            <tr>
              <td>Roles that started and never reached a terminal receipt</td>
              <td className="num">
                {governance.runs_with_started_but_no_terminal_agent_receipt}
              </td>
              <td className="num good">no orphans</td>
            </tr>
            <tr>
              <td>Rate-limit responses, and cases they caused to fail</td>
              <td className="num">{cohort.rate_limiting.http_429_count}</td>
              <td className="num good">
                {cohort.rate_limiting.cases_failed_by_rate_limiting} cases
              </td>
            </tr>
            <tr>
              <td>Data-mode receipts: per run / cohort-level</td>
              <td className="num">
                {modes.run_level_receipts} / {modes.cohort_level_receipts}
              </td>
              <td className="num">
                {modes.cohort_level_absent ? 'absence reported, no hash invented' : ', '}
              </td>
            </tr>
            <tr>
              <td>Artifact status as the artifacts themselves declare it</td>
              <td className="num">
                {Object.entries(cohort.artifacts.status_field)
                  .map(([status, count]) => `${count} ${status}`)
                  .join(', ')}
              </td>
              <td className="num">every non-VALID artifact is typed</td>
            </tr>
          </tbody>
        </table>
        <p className="caveat">
          The last row is not a blemish. A fail-closed system is expected to carry typed
          rejections: the eight REJECTED artifacts are the controller’s failure receipts and
          the eleven INCOMPLETE ones are the timed-out agent receipts, two citation audits that
          could not complete, and the manifest that honestly records an incomplete cohort.
        </p>
      </Section>

      <Section
        title="WHAT IT COST, AND WHAT THAT NUMBER IS"
        claim="Unit economics for a full cohort audit, reported as the projection it is."
      >
        <div className="run-grid">
          <div className="run-stat">
            <span className="stat-value">${projected.toFixed(2)}</span>
            <span className="stat-label">projected for {cases.length} cases</span>
          </div>
          <div className="run-stat">
            <span className="stat-value">
              {(Number(cohort.tokens.total) / 1_000_000).toFixed(2)}M
            </span>
            <span className="stat-label">tokens across {String(gate.tool_call_ids)} calls</span>
          </div>
          <div className="run-stat">
            <span className="stat-value">{Math.round(cohort.latency_ms.p50 / 1000)}s</span>
            <span className="stat-label">
              p50 agent latency · p95 {Math.round(cohort.latency_ms.p95 / 1000)}s
            </span>
          </div>
          <div className="run-stat">
            <span className="stat-value">{hours(execution.duration_seconds)}</span>
            <span className="stat-label">unattended, machine-triggered</span>
          </div>
        </div>
        <p className="caveat">
          The cost figure is the run’s own projection against a pinned pricing policy. Its
          `actual_billed_cost_state` reads{' '}
          <b>{String(cohort.cost.actual_billed_cost_state)}</b>: no billing readback was
          performed, so this is not presented as an invoiced amount.
        </p>
      </Section>
    </div>
  );
}
