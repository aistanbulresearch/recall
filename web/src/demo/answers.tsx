/**
 * The answers the demo can give, and the evidence each one stands on.
 *
 * Nothing here is generated when a question is asked. Every figure is read
 * from the committed generation-27 export at build time, so an answer is a
 * projection of stored artifacts rather than a model's account of them. If a
 * question falls outside what the artifacts can support, the demo says so
 * instead of improvising: which is the same rule the product itself follows.
 */

import type { ReactNode } from 'react';

import correctedView from '../data/p1-corrected-view.json';
import gemmaRunManifest from '../data/gemma-run-manifest.json';
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

/**
 * The frozen privacy study, read from the CORRECTED VIEW. Amendment 001 made
 * `surface_exact_search` the primary arm; the raw report still carries the
 * superseded declaration, so anything published must come from here plus the
 * committed erratum.
 */
const p1 = correctedView as unknown as {
  arms: Record<string, { arm: string; status: string }>;
  baseline: { combined: { document_level: Record<string, number> } };
  comparison_arm_b: { combined: { document_level: Record<string, number> } };
  structured_only_egress: { combined: { document_level: Record<string, number> } };
  frozen_test_run_id: string;
  record_count: number;
};

const gemmaRun = gemmaRunManifest as unknown as {
  receipt_count: number;
  elapsed_minutes: number;
  receipts_sha256: string;
  notes_sha256: string;
  verifier_lock_fingerprint_sha256: string;
  code_source_commit: string;
  locus: Record<string, string>;
};

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
    id: 'about',
    label: 'What is Recall?',
    keywords: [
      'what is recall',
      'what is this',
      'about',
      'tell me about',
      'explain the project',
      'overview',
      'introduce',
    ],
    body: (
      <>
        <p>
          Recall watches closed genomic cases after the appointment ends. When a genetic result
          is filed as <b>uncertain</b>, nobody is assigned to re-read it, and the evidence that
          would settle it arrives years later, in a public database, with no connection to the
          chart it should change.
        </p>
        <p>
          A fleet of agents with separated duties keeps looking: one finds new public evidence, a
          second judges whether it is material for that case, a third independently re-opens
          every source and verifies the citations. None of them decides. A deterministic policy
          gate reads their signed receipts and rules, and only a human specialist may act.
        </p>
        <p>
          Everything on this page comes from one real execution of that fleet on Google Cloud:{' '}
          {cases.length} cases, {hours(execution.duration_seconds)}, unattended.
        </p>
      </>
    ),
  },
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
            <b>{counts.NO_ACTION}</b> cases: nothing to raise. The public evidence for that
            case had not moved.
          </li>
          <li>
            <b>{counts.ABSTAIN}</b> cases: the fleet refused to decide, because the proof was
            incomplete.
          </li>
          <li>
            <b>{counts.HALTED}</b> cases: the machinery could not be trusted for that case, so
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
            the role timed out, <code>{sampleHalted.agent_execution_receipt.technical_code}</code>{' '}
            on a receipt that stays in the ledger
          </li>
          <li>
            the controller wrote a failure receipt, {' '}
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
          Failures landed on three different roles, {funnel[0].failed} watcher,{' '}
          {funnel[1].failed} assessor, {funnel[2].failed} auditor, and each one is traceable to
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
, and nothing else. The {halted.length} halted cases produced <b>no</b> policy decision
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
    keywords: [
      'auditor can check',
      'governance',
      'audit trail',
      'what can i check',
      'what can an auditor',
      'counted from',
    ],
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
            <b>{governance.distinct_trace_ids}</b> trace chains: one per case, {' '}
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
          . That is not a blemish; the rejected ones are the controller’s failure receipts, and
          a fail-closed system is supposed to carry typed rejections.
        </p>
      </>
    ),
    more: { href: '#/run', label: 'Open the auditor’s table' },
  },
  {
    id: 'why',
    label: 'Why does any of this matter?',
    keywords: [
      'why',
      'matter',
      'problem',
      'patient',
      'clinic',
      'purpose',
      'vus',
      'uncertain significance',
      'who is the user',
      'who benefits',
      'who is it for',
    ],
    body: (
      <>
        <p>
          A cancer patient’s genetic test can come back <b>“uncertain significance”</b>, a
          result that means <i>do not act, wait for evidence</i>. It cannot guide screening,
          cannot guide prevention, and cannot be used to test her relatives.
        </p>
        <p>
          The evidence that would settle it does arrive. On the case Recall replays, a variant
          in {hero.gene}, laboratory data went public on {hero.dates.geo_public} and the public
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
          residual spans they might have missed, and deterministic adjudication, not the model,
          decides what is redacted. What travels is a structured, minimized, hash-bound payload
          with a signed receipt.
        </p>
        <p>
          In this run, <b>{modes.run_level_receipts}</b> data-mode receipts record how each case
          was processed. A cohort-level receipt does not exist for this run, and its absence is
          reported rather than filled in with an invented hash.
        </p>
        <p className="quiet">
          A local Gemma proposes the residual spans the deterministic layer misses, and a frozen
          study measures exactly what that adds. Ask <b>what the local model actually adds</b>
          for the figures and their provenance.
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
          for {cases.length} cases, about{' '}
          {((Number(cohort.cost.projected_usd_micros) / 1_000_000 / cases.length) * 100).toFixed(
            1,
          )}{' '}
          cents each, across{' '}
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
  {
    id: 'stack',
    label: 'What is it built on?',
    keywords: [
      'built on',
      'technology',
      'tech stack',
      'stack',
      'google cloud',
      'gcp',
      'gemini',
      'vertex',
      'cloud run',
      'firestore',
      'adk',
      'what model',
      'which services',
      'infrastructure',
    ],
    body: (
      <>
        <p>Google Cloud carries the critical path, not a side path:</p>
        <ul>
          <li>
            <b>Cloud Run Job</b> runs the cohort as one long-lived execution, this one for{' '}
            {hours(execution.duration_seconds)}, started by a scheduler, not by a person.
          </li>
          <li>
            <b>Firestore</b> is the authoritative ledger: the durable watch case, every
            independent scan run, and an append-only artifact trail the agents cannot rewrite.
          </li>
          <li>
            <b>{String(cohort.runtime.runtime_class)}</b>: the agent runtime executes in process
            inside that job, with {String(cohort.runtime.concurrency)} cases in flight.
          </li>
          <li>
            <b>{String(cohort.runtime.model_id)}</b> through{' '}
            <b>{String(cohort.runtime.endpoint_class)}</b> for the reasoning roles, under the
            execution profile <code>{String(cohort.runtime.execution_profile)}</code>.
          </li>
          <li>
            A <b>local Gemma</b> handles residual-span detection at the privacy boundary, so note
            text never has to leave the laboratory to be screened.
          </li>
        </ul>
        <p className="quiet">
          Median agent latency in this run was {Math.round(cohort.latency_ms.p50 / 1000)}s, p95{' '}
          {Math.round(cohort.latency_ms.p95 / 1000)}s.
        </p>
      </>
    ),
  },
  {
    id: 'registry',
    label: 'How would another team find and reuse these agents?',
    keywords: [
      'registry',
      'discover',
      'discovery',
      'another team',
      'another department',
      'reuse',
      'catalog',
      'catalogue',
      'adopt',
      'consumer',
    ],
    body: (
      <>
        <p>
          A consuming team asks for a <b>capability</b>, not a URL. Resolution returns the binding
          together with the mode it was found by, <code>REGISTERED</code> when the agent reached
          the catalog through <code>agents.create</code>, <code>MANUAL_SERVICE</code> when it was
          registered as a service, and <code>PINNED_FALLBACK</code> when an endpoint was pinned
          outside the catalog. The catalog record is digest-addressed, so a changed catalog is
          detectable, and a capability with no entry is recorded as unresolved rather than
          quietly substituted.
        </p>
        <p>
          This run produced a resolution receipt for every one of its {cases.length} cases, and
          all of them record <code>PINNED_FALLBACK</code> with{' '}
          <code>validation_status: PASS</code>.
        </p>
        <p className="quiet">
          That is the honest reading: in this execution the endpoints were pinned, not catalogued
, and the registry said so on every case rather than presenting a pinned endpoint as a
          catalogued one. Cross-department discovery is proven as a mechanism in the source and
          in the receipt contract; it is not claimed as catalogue-resolved in this run.
        </p>
      </>
    ),
  },
  {
    id: 'memory',
    label: 'How does it remember between scans?',
    keywords: [
      'remember',
      'memory',
      'persistent',
      'persistence',
      'between scans',
      'next time',
      'long-running',
      'long running',
      'watchcase',
      'memory bank',
      'keeps state',
    ],
    body: (
      <>
        <p>
          Two lifetimes, deliberately separated. A <b>watch case</b> is durable and outlives any
          single scan; a <b>scan run</b> is bounded and has its own terminal state. This execution
          carried <b>{cohort.watch_cases_in_ledger}</b> watch cases and <b>{cases.length}</b> scan
          runs: one bounded attempt per durable case.
        </p>
        <p>
          Continuity lives in Firestore, not in a model's context window: source cursors, the last
          verified snapshot, pending observations and the case's own state. A scan that halts
          leaves the case intact and scannable again; nothing about the next scan depends on what
          a model happened to still have in memory.
        </p>
        <p className="quiet">
          A managed Memory Bank is deliberately not part of this. The architecture admits only
          non-authoritative operational context there, and no such runtime is deployed or claimed
. Firestore is the authority.
        </p>
      </>
    ),
  },
  {
    id: 'identity',
    label: 'What stops an agent doing something it should not?',
    keywords: [
      'permission',
      'identity',
      'iam',
      'service account',
      'stops an agent',
      'not allowed',
      'privilege',
      'least privilege',
      'gateway',
      'authoriz',
      'guardrail',
    ],
    body: (
      <>
        <p>Four boundaries, none of which is a prompt instruction:</p>
        <ul>
          <li>
            Each role runs under its <b>own service identity</b> with a role-scoped capability.
          </li>
          <li>
            The agents hold <b>no write access to the ledger at all</b>; they cannot record their
            own conclusions.
          </li>
          <li>
            Every tool call passes an authorization gate that emits a receipt. Without a receipt
            there is no backend authority. This run: {String(gate.tool_call_ids)} calls,{' '}
            {String(gate.tool_authorization_receipts)} receipts,{' '}
            {governance.tool_calls_without_authorization} unauthorized.
          </li>
          <li>
            The agent that proposes is never the agent that verifies, and neither can end a case,
            only the deterministic gate can.
          </li>
        </ul>
        <p className="quiet">
          Account names, project identifiers and endpoint ids are deliberately not published on
          this page.
        </p>
      </>
    ),
  },
  {
    id: 'observability',
    label: 'If something goes wrong, can you reconstruct it?',
    keywords: [
      'observab',
      'observe',
      'observing',
      'trace',
      'tracing',
      'reconstruct',
      'debug',
      'incident',
      'logs',
      'telemetry',
      'monitoring',
      'root cause',
    ],
    body: (
      <>
        <p>
          Yes, per case. This run recorded <b>{governance.distinct_trace_ids}</b> trace chains:
          one for each case, with <b>{governance.runs_with_more_than_one_trace}</b> mismatches and{' '}
          <b>{governance.agent_receipts_without_trace}</b> untraced agent receipts.
        </p>
        <p>
          For any single case you can recover which roles started and finished, what each tool
          call was authorized to do, the artifacts produced with their schema, producer and
          content hash, the gate's outcome and reason codes, and, where it applies, the failure
          receipt with the stage it names. That is why the eight timeouts are a story rather than
          a mystery.
        </p>
        <p className="quiet">
          {cohort.rate_limiting.http_429_count} rate-limit responses were absorbed during the run,
          and {cohort.rate_limiting.cases_failed_by_rate_limiting} cases failed because of one.
          Retries and failures are counted separately on purpose.
        </p>
      </>
    ),
  },
  {
    id: 'innovation',
    label: 'What is actually new here?',
    keywords: [
      'innovat',
      'new here',
      'different',
      'novel',
      'unique',
      'chatbot',
      'what makes',
      'special',
      'why not just',
    ],
    body: (
      <>
        <p>Not the model, and not the prompt. Three things:</p>
        <ul>
          <li>
            <b>The authority boundary is architecture, not instruction.</b> Agents cannot write
            the ledger, cannot authorize their own tools, and cannot end a case. That holds even
            if a model behaves badly, because it is enforced by identity and by a deterministic
            gate rather than by asking nicely.
          </li>
          <li>
            <b>Refusal is a first-class outcome with its own types.</b> ABSTAIN means the proof
            was incomplete; HALTED means the machinery could not be trusted. They are never
            collapsed into one another, and neither can produce an action. This run used both.
          </li>
          <li>
            <b>Nothing is claimed that an artifact does not carry.</b> Every figure on this page
            resolves to a stored artifact with a content hash, including the uncomfortable ones:
            eight technical terminals, a manifest that reads INCOMPLETE, and a cost that says it
            was never verified against billing.
          </li>
        </ul>
        <p>
          The fleet is also unattended: a scheduler starts it, it runs for hours, and no human is
          in the loop until a case is worth a specialist's time.
        </p>
      </>
    ),
  },
  {
    id: 'scale',
    label: 'Does this scale?',
    keywords: [
      'scale',
      'scaling',
      'hospital',
      'bigger',
      'thousands',
      'throughput',
      'production',
      'how fast',
      'how long did it take',
      'duration',
    ],
    body: (
      <>
        <p>
          What is measured: {cases.length} cases in {hours(execution.duration_seconds)} at a
          concurrency of {String(cohort.runtime.concurrency)}, for a projected $
          {(Number(cohort.cost.projected_usd_micros) / 1_000_000).toFixed(2)}, about{' '}
          {((Number(cohort.cost.projected_usd_micros) / 1_000_000 / cases.length) * 100).toFixed(1)}{' '}
          cents per case. Median agent latency {Math.round(cohort.latency_ms.p50 / 1000)}s.
        </p>
        <p>
          The shape of the work scales sideways: cases are independent, each has its own bounded
          scan and its own trace, and the ledger is append-only. Concurrency is a setting rather
          than a rewrite.
        </p>
        <p className="quiet">
          What is not measured: behaviour at a hospital's real volume, cost at that volume, or
          rate limits under heavier concurrency. This run is one cohort of {cases.length}{' '}
          synthetic cases, and nothing here is a throughput promise.
        </p>
      </>
    ),
  },
  {
    id: 'verify',
    label: 'How can I check any of this myself?',
    keywords: [
      'verify',
      'check it myself',
      'prove',
      'proof',
      'see the code',
      'source code',
      'repository',
      'repo',
      'open source',
      'hash',
      'reproduce',
    ],
    body: (
      <>
        <p>
          Every figure on this page comes from a committed export of the run, and every artifact
          in it carries its own <b>content hash</b>. The export lives beside the code, so the
          hashes can be recomputed from the bytes rather than taken on trust.
        </p>
        <p>
          The export also records how it was produced: the deployed source commit
          (<code>{execution.deployed.source_commit.slice(0, 12)}</code>), the image digest, the
          parser used to read the artifacts, and the fact that it performed zero writes. The run's
          recovery prefix was re-derived from an immutable launch receipt rather than discovered
          by scanning, and the Cloud Run execution was identified by exclusion from that receipt's
          own baseline, not by taking the most recent one.
        </p>
        <p className="quiet">
          Identifiers in the export are deterministic non-reversible aliases; the hashes are real.
          The repository and the recorded Cloud Console walkthrough are linked from the
          submission.
        </p>
      </>
    ),
    more: { href: '#/run', label: "See the run's binding and hashes" },
  },
  {
    id: 'architecture',
    label: 'Show me the architecture',
    keywords: [
      'architecture',
      'diagram',
      'design',
      'how is it built',
      'components',
      'system design',
      'topology',
    ],
    body: (
      <>
        <p>Two trust boundaries and a person:</p>
        <ul>
          <li>
            <b>Inside the laboratory:</b> synthetic institutional notes, deterministic detectors,
            a local Gemma proposing residual spans, deterministic adjudication and redaction, a
            structured-only egress gate, and a signed privacy receipt. The note text does not
            cross this line.
          </li>
          <li>
            <b>Inside Google Cloud:</b> the scheduler and the Cloud Run Job, the deterministic
            controller, registry resolution, the three agent roles, the tool gateway with its
            receipts, the Firestore ledger, the deterministic policy gate, and tracing.
          </li>
          <li>
            <b>The human:</b> a simulated review task, a specialist surface, and the final
            decision: which is never the system's.
          </li>
        </ul>
        <p>
          Models live inside the cloud boundary and may only propose. Deterministic code holds
          every decision.
        </p>
      </>
    ),
    more: { href: '#/story#how', label: 'The full architecture, drawn' },
  },
  {
    id: 'gemma',
    label: 'What does the local model actually add?',
    keywords: [
      'gemma',
      'local model',
      'small model',
      'on-device',
      'frozen',
      'measurement',
      'study',
      'redaction',
      'residual',
      'what does the local model',
      'why two models',
    ],
    body: (
      <>
        <p>
          Deterministic detectors alone are safe but blunt. On the frozen study of{' '}
          <b>{p1.record_count}</b> synthetic records, the deterministic-only baseline let{' '}
          <b>{p1.baseline.combined.document_level.accepted}</b> records through the egress gate,
          everything else was quarantined as possibly still carrying an identifier.
        </p>
        <p>
          With a <b>local Gemma</b> proposing the residual spans the deterministic layer missed,
          and deterministic adjudication deciding what to do with those proposals,{' '}
          <b>{p1.comparison_arm_b.combined.document_level.accepted}</b> of {p1.record_count}{' '}
          records became releasable, with{' '}
          <b>{p1.comparison_arm_b.combined.document_level.escaped_direct_identifier_surfaces}</b>{' '}
          escaped direct identifiers. The model widens what can be shared; it never decides what
          is safe.
        </p>
        <p className="quiet">
          Arm labels as amendment 001 fixed them: <code>{p1.arms.primary.arm}</code> is{' '}
          {p1.arms.primary.status}, <code>{p1.arms.secondary.arm}</code> is{' '}
          {p1.arms.secondary.status}. Figures come from the corrected view and the committed
          erratum, not from the raw manifest, whose arm declarations were superseded.
        </p>
        <p>
          Separately, the whole portfolio, <b>{gemmaRun.receipt_count} cases</b>, was put
          through the real privacy gate with the Gemma leg live on a private endpoint, producing
          a signed receipt for every case in {Math.round(gemmaRun.elapsed_minutes)} minutes. Each
          receipt declares where it ran: <code>{gemmaRun.locus.execution_locus}</code> /{' '}
          <code>{gemmaRun.locus.transport_class}</code> /{' '}
          <code>{gemmaRun.locus.endpoint_class}</code>.
        </p>
        <p className="quiet">
          That receipt run is a <b>historical frozen measurement</b>, executed once at commit{' '}
          <code>{gemmaRun.code_source_commit.slice(0, 8)}</code>, not the current product commit{' '}
          <code>{execution.deployed.source_commit.slice(0, 8)}</code>. It is never re-run: the
          preregistration binds it to a single execution, so a new run would be a new experiment
          rather than a confirmation. It has been revalidated read-only against the current
          contract, {gemmaRun.receipt_count} of {gemmaRun.receipt_count} receipts parsed and
          signature-verified, zero writes, original bytes unchanged, and its{' '}
          {gemmaRun.receipt_count} cases are a different population from the {p1.record_count}{' '}
          study records. The two are never combined.
        </p>
      </>
    ),
  },
];

/**
 * Route a TYPED question to the closest answer, or to none.
 *
 * Longer keywords weigh more, so a specific word ("timeout") outranks a word
 * several answers share ("run"). A tie is not resolved by list order: it is
 * treated as no match, and the demo offers the options instead of guessing.
 * Clicking a suggestion never comes through here, those carry their id.
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
