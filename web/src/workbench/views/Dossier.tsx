/**
 * Evidence dossier: the auditor-grade view. The full derived-field surface
 * (Mission Control) per scenario bundle, with the provenance chain closing at
 * the bottom. This is the layer the substrate strip summarizes everywhere
 * else — here it is the whole page.
 */

import { useState } from 'react';

import { MissionControl } from '../../components/MissionControl';
import type { Scenario } from '../Workbench';
import type { ViewModel } from '../../viewmodel/types';

interface BuildResult {
  fields: ViewModel;
  acceptedArtifactCount: number;
  rejected: ReadonlyArray<{ artifact_id: string; schema_name: string; reason_code: string }>;
}

export function Dossier({
  scenarios,
  models,
}: {
  scenarios: readonly Scenario[];
  models: Record<string, BuildResult>;
}) {
  const [selectedId, setSelectedId] = useState(scenarios[0].id);
  const scenario = scenarios.find((s) => s.id === selectedId) ?? scenarios[0];
  const result = models[scenario.id];

  return (
    <section className="dossier">
      <header className="view-head">
        <h1>Evidence dossier</h1>
        <p className="view-sub">
          The unabridged derived-field surface for each scenario bundle. Selecting a bundle
          changes the input artifacts only — outcomes are never preset.
        </p>
      </header>

      <nav className="fixture-bar" aria-label="Input fixture">
        {scenarios.map((entry) => (
          <button
            key={entry.id}
            type="button"
            className={entry.id === selectedId ? 'fixture-button selected' : 'fixture-button'}
            aria-pressed={entry.id === selectedId}
            onClick={() => setSelectedId(entry.id)}
          >
            {entry.label}
          </button>
        ))}
      </nav>

      <MissionControl model={result.fields} />

      <footer className="provenance">
        <p>{scenario.bundle.provenance.note}</p>
        <p>
          Artifacts accepted: {result.acceptedArtifactCount}. Rejected by contract validation:{' '}
          {result.rejected.length}.
        </p>
        {result.rejected.length > 0 ? (
          <ul>
            {result.rejected.map((entry) => (
              <li key={entry.artifact_id}>
                <code>{entry.schema_name}</code> <code>{entry.reason_code}</code>
              </li>
            ))}
          </ul>
        ) : null}
      </footer>
    </section>
  );
}
