/**
 * Application shell.
 *
 * The fixture selector changes the input bundle only. It never selects an
 * outcome, a badge, a count, or a status: those are derived from the artifacts
 * inside whichever bundle is loaded.
 */

import { useMemo, useState } from 'react';

import faultBundle from './bundles/fault.json';
import goldenBundle from './bundles/golden.json';
import haltedBundle from './bundles/halted.json';
import { MissionControl } from './components/MissionControl';
import { buildViewModel } from './viewmodel/builder';
import type { ArtifactBundle } from './viewmodel/types';

const BUNDLES: ReadonlyArray<{ id: string; label: string; bundle: ArtifactBundle }> = [
  { id: 'golden', label: 'Audited replay fixture', bundle: goldenBundle as unknown as ArtifactBundle },
  { id: 'fault', label: 'Fault fixture: mismatched citation and forbidden tool request', bundle: faultBundle as unknown as ArtifactBundle },
  { id: 'halted', label: 'Fault fixture: ledger integrity unavailable', bundle: haltedBundle as unknown as ArtifactBundle },
];

/**
 * The information architecture requires a stable deep link and a refresh that
 * reconstructs the same screen. The query parameter therefore selects the input
 * fixture only; it can never select an outcome.
 */
function initialFixtureId(): string {
  if (typeof window === 'undefined') {
    return BUNDLES[0].id;
  }
  const requested = new URLSearchParams(window.location.search).get('fixture');
  return BUNDLES.some((entry) => entry.id === requested) ? String(requested) : BUNDLES[0].id;
}

export function App() {
  const [selectedId, setSelectedId] = useState(initialFixtureId);
  const selected = BUNDLES.find((entry) => entry.id === selectedId) ?? BUNDLES[0];
  const result = useMemo(() => buildViewModel(selected.bundle), [selected]);

  return (
    <div className="app">
      <nav className="fixture-bar" aria-label="Input fixture">
        <span className="fixture-label">Input fixture</span>
        {BUNDLES.map((entry) => (
          <button
            key={entry.id}
            type="button"
            className={entry.id === selectedId ? 'fixture-button selected' : 'fixture-button'}
            aria-pressed={entry.id === selectedId}
            onClick={() => {
              setSelectedId(entry.id);
              if (typeof window !== 'undefined') {
                const url = new URL(window.location.href);
                url.searchParams.set('fixture', entry.id);
                window.history.replaceState(null, '', url);
              }
            }}
          >
            {entry.label}
          </button>
        ))}
        <span className="fixture-note">
          Selecting a fixture changes the input artifacts only. Outcomes are never preset.
        </span>
      </nav>
      <MissionControl model={result.fields} />
      <footer className="provenance">
        <p>{selected.bundle.provenance.note}</p>
        <p>
          Artifacts accepted: {result.acceptedArtifactCount}. Rejected by contract validation: {result.rejected.length}.
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
    </div>
  );
}
