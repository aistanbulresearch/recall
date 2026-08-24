/** Fleet board version 0: roles, revisions, persisted states, and denials. */

import type { ViewField, ViewModel } from '../viewmodel/types';
import { authorizationCopy, reasonCodeCopy } from '../viewmodel/semantics';
import { FieldValue, formatValue } from './FieldValue';

interface Binding {
  capability?: string;
  agent_id?: string;
  role?: string;
  revision?: string;
  validation_status?: string;
}

function bindings(field: ViewField): Binding[] {
  return field.items.filter((item): item is Binding => typeof item === 'object' && item !== null);
}

export function FleetBoard({ model }: { model: ViewModel }) {
  const roster = model['UI-AGENT-ROSTER'];
  const agentStates = model['UI-AGENT-STATE'];
  const denial = model['UI-TOOL-DENIAL'];

  return (
    <section className="panel panel-fleet" aria-labelledby="fleet-heading">
      <h2 id="fleet-heading">Agent lanes</h2>
      <p className="panel-copy">
        A lane appears only when the registry resolved that exact agent revision for this run. Agents propose and audit.
        They cannot write state or create a terminal outcome.
      </p>
      {roster.status === 'KNOWN' ? (
        <table className="roster">
          <thead>
            <tr>
              <th scope="col">Role</th>
              <th scope="col">Agent</th>
              <th scope="col">Revision</th>
              <th scope="col">Binding</th>
            </tr>
          </thead>
          <tbody>
            {bindings(roster).map((binding) => (
              <tr key={String(binding.agent_id)}>
                <td>{binding.role ?? 'INCOMPLETE'}</td>
                <td>{binding.agent_id ?? 'INCOMPLETE'}</td>
                <td>{binding.revision ?? 'INCOMPLETE'}</td>
                <td>{binding.validation_status ?? 'INCOMPLETE'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <p className="panel-empty">{roster.status}: no validated binding resolved, so no lane is drawn.</p>
      )}

      <div className="field-grid">
        <FieldValue field={model['UI-ROUTE-STATUS']} />
        <FieldValue field={model['UI-CLOUD-REGISTRY-COUNT']} />
        <FieldValue field={model['UI-CLOUD-TRANSITIONS']} />
        <FieldValue field={model['UI-WATCH-SCAN-COUNT']} />
      </div>

      {agentStates.status === 'KNOWN' ? (
        <ol className="transitions" data-field-id={agentStates.field_id}>
          {agentStates.items.map((state, index) => (
            <li key={`${String(state)}-${index}`}>{String(state)}</li>
          ))}
        </ol>
      ) : (
        <p className="panel-empty">{agentStates.status}: no persisted transition resolved.</p>
      )}

      {denial.hidden && denial.status !== 'KNOWN' ? null : (
        <div className="denial" data-field-id={denial.field_id} data-status={denial.status}>
          <h3>Blocked action</h3>
          <p>
            <strong>{formatValue(denial)}</strong> — {authorizationCopy(denial.value).plain}
          </p>
          <dl className="denial-detail">
            {denial.items
              .filter((entry): entry is { property: string; value: unknown } =>
                typeof entry === 'object' && entry !== null && 'property' in entry,
              )
              .map((entry) => (
                <div key={entry.property}>
                  <dt>{entry.property}</dt>
                  <dd>
                    {Array.isArray(entry.value)
                      ? entry.value.map((code) => (
                          <span key={String(code)} className="reason-code">
                            <code>{String(code)}</code> {reasonCodeCopy(String(code))}
                          </span>
                        ))
                      : String(entry.value)}
                  </dd>
                </div>
              ))}
          </dl>
          <FieldValue field={denial} />
        </div>
      )}
    </section>
  );
}
