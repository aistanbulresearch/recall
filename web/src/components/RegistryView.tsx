/** Registry view: which agent revisions were resolved and bound for this run. */

import type { ViewModel } from '../viewmodel/types';
import { FieldValue } from './FieldValue';

interface Binding {
  capability?: string;
  agent_id?: string;
  role?: string;
  revision?: string;
  region?: string;
  manifest_digest?: string;
  binding_id?: string;
  validation_status?: string;
}

export function RegistryView({ model }: { model: ViewModel }) {
  const roster = model['UI-AGENT-ROSTER'];
  const bindings = roster.items.filter((item): item is Binding => typeof item === 'object' && item !== null);
  return (
    <section className="panel panel-registry" aria-labelledby="registry-heading">
      <h2 id="registry-heading">Registry resolution</h2>
      <p className="panel-copy">
        The deterministic controller resolves each capability through the registry and records the exact revision it
        invoked. A binding that did not validate is never drawn as a working lane.
      </p>
      <div className="field-grid">
        <FieldValue field={model['UI-CLOUD-REGISTRY-COUNT']} />
      </div>
      {roster.status === 'KNOWN' ? (
        <ul className="bindings">
          {bindings.map((binding) => (
            <li key={String(binding.binding_id ?? binding.agent_id)}>
              <code>{binding.capability ?? 'INCOMPLETE'}</code> → <code>{binding.agent_id ?? 'INCOMPLETE'}</code>{' '}
              <code>{binding.revision ?? 'INCOMPLETE'}</code>{' '}
              <span className="binding-region">{binding.region ?? 'INCOMPLETE'}</span>{' '}
              <span className="binding-status">{binding.validation_status ?? 'INCOMPLETE'}</span>
              <br />
              <code className="lineage-hash">{binding.manifest_digest ?? 'INCOMPLETE'}</code>
            </li>
          ))}
        </ul>
      ) : (
        <p className="panel-empty">{roster.status}: no registry resolution receipt resolved.</p>
      )}
    </section>
  );
}
