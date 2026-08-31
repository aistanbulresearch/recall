/**
 * The answers the demo can give, and the evidence each one stands on.
 *
 * Nothing here is generated when a question is asked. Every figure is read
 * from the committed generation-27 export at build time, so an answer is a
 * projection of stored artifacts rather than a model's account of them. If a
 * question falls outside what the artifacts can support, the demo says so
 * instead of improvising — which is the same rule the product itself follows.
 */

import type { ReactNode } from 'react';

import historicalCase from '../data/historical-case.json';
import {
  cohort,
  distributionFromCases,
  execution,
  manifest,
  modes,
  readBundle,
  roleFunnel,
} from '../run/runBundle';

const { cases, halted } = readBundle();
const counts = distributionFromCases(cases);
const governance = cohort.governance_checks;
const gate = cohort.tool_and_gateway;
const funnel = roleFunnel();
const decided = Object.values(governance.policy_outcomes_seen).reduce((a, b) => a + b, 0);

const hero = historicalCase as unknown as {
  dates: Record<string, string>;
  gene: string;
  variant: string;
  clinvar_vcv: string;
  honesty_sentences: string[];
};

function days(from: string, to: string): number {
  return Math.round(
    (Date.parse(`${to}T00:00:00Z`) - Date.parse(`${from}T00:00:00Z`)) / 86_400_000,
  );
}

const registryGap = days(hero.dates.geo_public, hero.dates.clinvar_v5_public);
const leadTime = days(hero.dates.qualifying_publication, hero.dates.clinvar_v5_public);

function hours(seconds: number): string {
  return `${Math.floor(seconds / 3600)}h ${Math.round((seconds % 3600) / 60)}m`;
}

/** A figure with the artifact it came from, shown on demand. */
export function Fact({ children, source }: { children: ReactNode; source: string }) {
  return (
    <span className="fact" title={source}>
      {children}
    </span>
  );
}

export interface Answer {
  id: string;
  /** What the juror clicks. */
  label: string;
  /** Words that route a typed question here. */
  keywords: string[];
  body: ReactNode;
  /** Where to go for the full picture, if anywhere. */
  more?: { href: string; label: string };
}

const sampleCase = cases.find((row) => row.state === 'ABSTAIN') ?? cases[0];
const sampleHalted = halted[0];

export const ANSWERS: Answer[] = [
  {
    id: 'run',
    label: 'What happened in the run?',
    keywords: ['the run', 'execution', 'overall', 'summary', 'how many cases', 'what happened in the run'],
    body: (
      <>
        <p>
          One Cloud Run Job took <b>{cases.length} cases</b> through the fleet, unattended, for{' '}
          <b>{hours(execution.duration_seconds)}</b>. It finished at {execution.completed_at}.
        </p>
        <ul>
          <li>
            <b>{counts.NO_ACTION}</b> cases — nothing to raise. The public evidence for that
            case had not moved.
          </li>
          <li>
            <b>{counts.ABSTAIN}</b> cases — the fleet refused to decide, because the proof was
            incomplete.
          </li>
          <li>
            <b>{counts.HALTED}</b> cases — the machinery could not be trusted for that case, so
            it stopped and recorded why.
          </li>
          <li>
            <b>{counts.REVIEW_REQUIRED}</b> cases reached a specialist. On this cohort, nothing
            crossed that bar.
          </li>
        </ul>
        <p>
          Cloud Run reports <b>{execution.terminal_state}</b> and the cohort manifest reports{' '}
          <b>{manifest.status}</b>. Both are true, and an infrastructure success is not an
          application success.
        </p>
      </>
    ),
    more: { href: '#/run', label: 'Open the run, case by case' },
  },
  {
    id: 'failure',
    label: 'What happened when something failed?',
    keywords: ['fail', 'failure', 'error', 'crash', 'halt', 'timeout', 'time out', 'times out', 'timed out', 'went wrong', 'break'],
    body: (
      <>
        <p>
          {halted.length} cases hit an agent timeout. None of them became an action, and none of
          them stopped the cohort.
        </p>
        <p>The chain closed the same way in all {halted.length}:</p>
        <ol className="chain">
          <li>
            the role timed out — <code>{sampleHalted.agent_execution_receipt.technical_code}</code>{' '}
            on a receipt that stays in the ledger
          </li>
          <li>
            the controller wrote a failure receipt —{' '}
            <code>{sampleHalted.failure_receipt.controller_code}</code>, stage{' '}
            <b>{sampleHalted.failure_receipt.stage}</b>, not retryable, with an operator action
          </li>
          <li>
            the case reached the technical terminal <b>HALTED</b>
          </li>
          <li>
            <b>
              {halted.reduce((sum, row) => sum + row.closure.policy_decisions, 0)}
            </b>{' '}
            policy decisions and{' '}
            <b>{halted.reduce((sum, row) => sum + row.closure.review_tasks, 0)}</b> review tasks
            were created from them
          </li>
          <li>the other {cases.length - halted.length} cases kept going</li>
        </ol>
        <p>
          Failures landed on three different roles — {funnel[0].failed} watcher,{' '}
          {funnel[1].failed} assessor, {funnel[2].failed} auditor — and each one is traceable to
          a case, a stage and a receipt hash.
        </p>
      </>
    ),
    more: { href: '#/run#containment', label: 'See all eight, with their receipts' },
  },
  {
    id: 'authority',
    label: 'Can a model’s output become an action?',
    keywords: ['become an action', 'hallucinat', 'authority', 'decide', 'decision', 'policy gate', 'trust the model'],
    body: (
      <>
        <p>
          No. Agents may propose and audit; only a deterministic policy gate can end a case, and
          it reads signed receipts rather than prose.
        </p>
        <p>
          In this run the gate emitted{' '}
          {Object.entries(governance.policy_outcomes_seen)
            .map(([outcome, count]) => `${count} ${outcome}`)
            .join(' and ')}{' '}
          — and nothing else. The {halted.length} halted cases produced <b>no</b> policy decision
          at all, and the ledger contains <b>{cohort.review_tasks_in_ledger}</b> review tasks.
        </p>
        <p>
          The {counts.ABSTAIN} abstentions are the interesting ones. A model produced a material
          claim, the Citation Auditor could not verify its sources, and the gate refused rather
          than rounding up. The reason codes it recorded:
        </p>
        <p className="codes">
          {sampleCase.policy_reason_codes.map((code) => (
            <code key={code}>{code}</code>
          ))}
        </p>
      </>
    ),
  },
  {
    id: 'agents',
    label: 'Who are the agents, and who checks them?',
    keywords: ['who are the agents', 'fleet', 'watcher', 'assessor', 'auditor', 'separation', 'roles'],
    body: (
      <>
        <p>
          Three roles with separated duties, each under its own service identity, none of them
          able to write the ledger:
        </p>
        <ul>
          <li>
            <b>Evidence Watcher</b> finds new public evidence and captures it as bytes.
          </li>
          <li>
            <b>Evidence Assessor</b> judges whether the change is material for that case.
          </li>
          <li>
            <b>Citation Auditor</b> independently re-opens every source and verifies the claims.
          </li>
        </ul>
        <p>
          The agent that proposes is never the agent that verifies, and neither decides. Every
          case that entered is accounted for: {funnel[0].started} started with the watcher,{' '}
          {funnel[1].started} reached the assessor, {funnel[2].started} reached the auditor, and{' '}
          {decided} reached the gate. Each drop is one recorded failure, not a gap.
        </p>
      </>
    ),
    more: { href: '#/run', label: 'See the funnel' },
  },
  {
    id: 'governance',
    label: 'What can an auditor actually check?',
    keywords: ['auditor can check', 'verify', 'governance', 'authorization', 'trace', 'audit trail', 'what can i check'],
    body: (
      <>
        <p>Everything below is counted from the run’s stored artifacts, not from a log line:</p>
        <ul className="checks">
          <li>
            <b>{cohort.artifacts.documents.toLocaleString('en-US')}</b> artifacts stored,{' '}
            <b>{cohort.artifacts.parsed_by_production_contract.toLocaleString('en-US')}</b>{' '}
            parsed by the deployed contract code, <b>{cohort.artifacts.parse_failures}</b>{' '}
            failures.
          </li>
          <li>
            <b>{String(gate.tool_call_ids)}</b> tool calls,{' '}
            <b>{String(gate.tool_authorization_receipts)}</b> authorization receipts,{' '}
            <b>{governance.tool_calls_without_authorization}</b> unauthorized.
          </li>
          <li>
            <b>{governance.distinct_trace_ids}</b> trace chains — one per case —{' '}
            {governance.runs_with_more_than_one_trace} mismatched,{' '}
            {governance.agent_receipts_without_trace} untraced.
          </li>
          <li>
            <b>{cohort.rate_limiting.http_429_count}</b> rate-limit responses absorbed,{' '}
            <b>{cohort.rate_limiting.cases_failed_by_rate_limiting}</b> cases failed because of
            one.
          </li>
          <li>
            <b>{governance.runs_with_started_but_no_terminal_agent_receipt}</b> roles started and
            never reached a terminal receipt.
          </li>
        </ul>
        <p>
          The artifacts also declare their own state:{' '}
          {Object.entries(cohort.artifacts.status_field)
            .map(([status, count]) => `${count} ${status}`)
            .join(', ')}
          . That is not a blemish — the rejected ones are the controller’s failure receipts, and
          a fail-closed system is supposed to carry typed rejections.
        </p>
      </>
    ),
    more: { href: '#/run', label: 'Open the auditor’s table' },
  },
  {
    id: 'why',
    label: 'Why does any of this matter?',
    keywords: ['why', 'matter', 'problem', 'patient', 'clinic', 'purpose', 'vus', 'uncertain significance'],
    body: (
      <>
        <p>
          A cancer patient’s genetic test can come back <b>“uncertain significance”</b> — a
          result that means <i>do not act, wait for evidence</i>. It cannot guide screening,
          cannot guide prevention, and cannot be used to test her relatives.
        </p>
        <p>
          The evidence that would settle it does arrive. On the case Recall replays — a variant
          in {hero.gene} — laboratory data went public on {hero.dates.geo_public} and the public
          record first moved on {hero.dates.clinvar_v5_public}. That is{' '}
          <b>{registryGap} days</b>, with <b>{leadTime} days</b> from the qualifying publication.
          Two intervals, two meanings, never one number.
        </p>
        <p className="quiet">{hero.honesty_sentences.join(' ')}</p>
        <p>Nobody’s job is to re-read a closed case. That is the job Recall does.</p>
      </>
    ),
    more: { href: '#/story', label: 'The full story, with sources' },
  },
  {
    id: 'privacy',
    label: 'What leaves the laboratory?',
    keywords: ['privacy', 'redact', 'laboratory', 'leaves the lab', 'leave the lab', 'gemma', 'personal data', 'patient data'],
    body: (
      <>
        <p>
          Not the note. Deterministic detectors screen every record, a local Gemma proposes the
          residual spans they might have missed, and deterministic adjudication — not the model —
          decides what is redacted. What travels is a structured, minimized, hash-bound payload
          with a signed receipt.
        </p>
        <p>
          In this run, <b>{modes.run_level_receipts}</b> data-mode receipts record how each case
          was processed. A cohort-level receipt does not exist for this run, and its absence is
          reported rather than filled in with an invented hash.
        </p>
        <p className="quiet">
          Separately, a frozen 462-case measurement at an earlier commit put the whole portfolio
          through the privacy gate with the Gemma leg live. It is a historical measurement, never
          re-run, and it is labelled as one wherever it appears.
        </p>
      </>
    ),
    more: { href: '#/story#platform', label: 'The privacy boundary' },
  },
  {
    id: 'cost',
    label: 'What did it cost to run?',
    keywords: ['cost', 'price', 'money', 'token', 'spend', 'economics', 'cheap', 'expensive'],
    body: (
      <>
        <p>
          <b>${(Number(cohort.cost.projected_usd_micros) / 1_000_000).toFixed(2)}</b> projected
          for {cases.length} cases — about{' '}
          {((Number(cohort.cost.projected_usd_micros) / 1_000_000 / cases.length) * 100).toFixed(
            1,
          )}{' '}
          cents each — across{' '}
          <b>{(Number(cohort.tokens.total) / 1_000_000).toFixed(2)}M</b> tokens and{' '}
          {String(gate.tool_call_ids)} tool calls, over {hours(execution.duration_seconds)}.
        </p>
        <p className="quiet">
          That figure is the run’s own projection against a pinned pricing policy. Its{' '}
          <code>actual_billed_cost_state</code> reads <b>{String(cohort.cost.actual_billed_cost_state)}</b>
          : no billing readback was performed, so it is not an invoiced amount.
        </p>
      </>
    ),
  },
  {
    id: 'limits',
    label: 'What can’t you prove?',
    keywords: ['limit', 'cannot prove', "can't prove", 'weakness', 'not proven', 'caveat', 'what is missing'],
    body: (
      <>
        <p>The things this demo deliberately does not claim:</p>
        <ul>
          <li>
            <b>Actual billed cost.</b> A projection exists; the run’s own state field says it was
            never verified against billing.
          </li>
          <li>
            <b>A completed cohort.</b> The manifest’s own status is {manifest.status}, because{' '}
            {counts.HALTED} cases never reached a decision.
          </li>
          <li>
            <b>A Memory Bank runtime.</b> The boundary is a rule in the architecture, not a
            deployed component, and it is marked deferred.
          </li>
          <li>
            <b>Model Armor in this run.</b> The mechanism is in the source; no live capture is
            attached, so no activity is attributed to this execution.
          </li>
          <li>
            <b>Why those agents timed out.</b> The containment is proven; the cause is tracked
            separately rather than guessed at here.
          </li>
          <li>
            <b>Clinical use of any kind.</b> This is a non-clinical research prototype on
            synthetic institutional records and captured public evidence.
          </li>
        </ul>
      </>
    ),
  },
  {
    id: 'case',
    label: 'Show me one case in detail',
    keywords: ['one case', 'a case', 'single case', 'example', 'case in detail', 'show me a case'],
    body: (
      <>
        <p>
          Case <code>{sampleCase.case}</code>, which ended in <b>{sampleCase.state}</b> with{' '}
          {sampleCase.artifact_count} artifacts recorded.
        </p>
        <ul>
          <li>
            roles:{' '}
            {Object.entries(sampleCase.roles)
              .map(([role, status]) => `${role.replace('EVIDENCE_', '').replace('CITATION_', '')} ${status}`)
              .join(' · ')}
          </li>
          <li>
            gate reason codes:{' '}
            {sampleCase.policy_reason_codes.map((code) => (
              <code key={code}>{code}</code>
            ))}
          </li>
          <li>
            privacy receipt{' '}
            <code>{(sampleCase.receipts.privacy_receipt_hash ?? '').slice(0, 12)}…</code>, policy
            decision{' '}
            <code>{(sampleCase.receipts.policy_decision_hash ?? '').slice(0, 12)}…</code>
          </li>
        </ul>
        <p className="quiet">
          Identifiers are deterministic aliases; the hashes are the real content hashes from the
          ledger, so any row can be checked against the stored artifact.
        </p>
      </>
    ),
    more: { href: '#/run', label: 'Browse all 456' },
  },
];

/**
 * Route a TYPED question to the closest answer, or to none.
 *
 * Longer keywords weigh more, so a specific word ("timeout") outranks a word
 * several answers share ("run"). A tie is not resolved by list order: it is
 * treated as no match, and the demo offers the options instead of guessing.
 * Clicking a suggestion never comes through here — those carry their id.
 */
export function match(input: string): Answer | null {
  const text = input.toLowerCase();
  const scored = ANSWERS.map((answer) => ({
    answer,
    score: answer.keywords.reduce(
      (sum, keyword) => (text.includes(keyword) ? sum + keyword.length : sum),
      0,
    ),
  }))
    .filter((entry) => entry.score > 0)
    .sort((left, right) => right.score - left.score);

  if (scored.length === 0) {
    return null;
  }
  if (scored.length > 1 && scored[0].score === scored[1].score) {
    return null;
  }
  return scored[0].answer;
}

export function byId(id: string): Answer | null {
  return ANSWERS.find((answer) => answer.id === id) ?? null;
}
