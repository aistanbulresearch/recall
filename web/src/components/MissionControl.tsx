/** Primary single-screen surface. Every result value comes from the view model. */

import type { ViewModel } from '../viewmodel/types';
import { reasonCodeCopy } from '../viewmodel/semantics';
import { DataModeBadge, PolicyOutcomeBadge, RunStateBadge } from './Badges';
import { FieldValue, formatValue } from './FieldValue';
import { EvidenceCard } from './EvidenceCard';
import { FleetBoard } from './FleetBoard';
import { PrivacyPanel } from './PrivacyPanel';
import { RegistryView } from './RegistryView';

function ReasonList({ model, fieldId, heading }: { model: ViewModel; fieldId: string; heading: string }) {
  const field = model[fieldId];
  return (
    <div className="reasons" data-field-id={field.field_id} data-status={field.status}>
      <h3>{heading}</h3>
      {field.status === 'KNOWN' && field.items.length === 0 ? (
        <p className="panel-empty">None recorded in the deterministic decision.</p>
      ) : null}
      {field.status === 'KNOWN' && field.items.length > 0 ? (
        <ul>
          {field.items.map((code) => (
            <li key={String(code)}>
              <code>{String(code)}</code> <span>{reasonCodeCopy(String(code))}</span>
            </li>
          ))}
        </ul>
      ) : null}
      {field.status === 'KNOWN' ? null : (
        <p className="panel-empty">{field.status}: no deterministic reason resolved. No explanation is generated.</p>
      )}
    </div>
  );
}

export function MissionControl({ model }: { model: ViewModel }) {
  return (
    <main className="mission-control">
      <header className="masthead">
        <div className="masthead-identity">
          <h1>Recall</h1>
          <p className="prototype-label">NON-CLINICAL RESEARCH PROTOTYPE — synthetic institutional records only</p>
        </div>
        <div className="masthead-fields">
          <DataModeBadge field={model['UI-GLOBAL-MODE']} />
          <RunStateBadge field={model['UI-GLOBAL-RUN-STATE']} />
          <FieldValue field={model['UI-GLOBAL-RUN-ID']} />
          <FieldValue field={model['UI-GLOBAL-TRACE-ID']} />
          <FieldValue field={model['UI-CLOUD-RUNTIME-REV']} />
          <FieldValue field={model['UI-CLOUD-HEALTH']} />
          <FieldValue field={model['UI-GLOBAL-UPDATED']} />
        </div>
      </header>

      <div className="board">
        <section className="panel panel-watch" aria-labelledby="watch-heading">
          <h2 id="watch-heading">Specialist review queue</h2>
          <p className="panel-copy">
            A watch case stays open for weeks without a running model process. Each scan is short, bounded, and
            independently auditable.
          </p>
          <div className="field-grid">
            <FieldValue field={model['UI-WATCH-STATUS']} />
            <FieldValue field={model['UI-WATCH-LAST-SCAN']} />
            <FieldValue field={model['UI-WATCH-NEXT-SCAN']} />
            <FieldValue field={model['UI-WATCH-PENDING']} hint="Unverified evidence is retained, never cleared by a failure." />
          </div>
          {model['UI-WATCH-ATTENTION'].status === 'KNOWN' ? (
            <ReasonList model={model} fieldId="UI-WATCH-ATTENTION" heading="Attention" />
          ) : null}
        </section>

        <EvidenceCard />

        <FleetBoard model={model} />

        <section className="panel panel-safety" aria-labelledby="safety-heading">
          <h2 id="safety-heading">Independent audit and deterministic authority</h2>
          <p className="panel-copy">
            A second agent independently reopened every source. Only deterministic policy may end a run, and only a
            clinician may act on the result.
          </p>
          <div className="field-grid">
            <FieldValue field={model['UI-EVIDENCE-CANDIDATE']} />
            <FieldValue field={model['UI-EVIDENCE-CLASS-UNCHANGED']} />
            <FieldValue field={model['UI-CITATION-TOTAL']} />
            <FieldValue field={model['UI-CITATION-VERIFIED']} />
            <FieldValue field={model['UI-CITATION-STATUS']} />
          </div>
        </section>

        <section className="panel panel-policy" aria-labelledby="policy-heading">
          <h2 id="policy-heading">Deterministic outcome</h2>
          <PolicyOutcomeBadge field={model['UI-POLICY-OUTCOME']} />
          <ReasonList model={model} fieldId="UI-POLICY-REASONS" heading="Why" />
          <ReasonList model={model} fieldId="UI-POLICY-MISSING" heading="Missing proof" />
          <div className="field-grid">
            <FieldValue field={model['UI-TASK-COUNT-RUN']} hint="Counted from the task ledger, never inferred from the outcome." />
            {model['UI-TASK-STATE'].hidden && model['UI-TASK-STATE'].status !== 'KNOWN' ? null : (
              <FieldValue field={model['UI-TASK-STATE']} hint="Simulated workflow artifact. Never a real clinical task." />
            )}
          </div>
          <p className="authority-note">
            Recall does not classify a variant, change a report, or contact a patient. The clinician remains the final
            authority. Simulated task state: {formatValue(model['UI-TASK-STATE'])}.
          </p>
        </section>

        <PrivacyPanel model={model} />
        <RegistryView model={model} />
      </div>
    </main>
  );
}
