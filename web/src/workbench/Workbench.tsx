/**
 * Recall Clinical Evidence Workbench — the hosted panel shell.
 *
 * Two permanent layers:
 *   above — a clinician-facing laboratory workbench (worklist, case records,
 *           cohort ledger, privacy desk, evidence dossier);
 *   below — the evidence substrate strip: the same figures with their full
 *           lineage (json path, artifact id, content hash), always visible.
 *
 * Navigation is hash-based so the build serves from any static host with no
 * rewrite rules. A route can never select an outcome — it selects which
 * derived record is on screen.
 */

import { useEffect, useMemo, useState } from 'react';

import './workbench.css';

import faultBundle from '../bundles/fault.json';
import goldenBundle from '../bundles/golden.json';
import haltedBundle from '../bundles/halted.json';
import { buildViewModel } from '../viewmodel/builder';
import type { ArtifactBundle } from '../viewmodel/types';

import { EvidenceStrip, StripProvider } from './strip';
import { Walkthrough } from './views/Walkthrough';
import { Worklist } from './views/Worklist';
import { CaseRecord } from './views/CaseRecord';
import { HeroCase } from './views/HeroCase';
import { CohortLedger } from './views/CohortLedger';
import { PrivacyDesk } from './views/PrivacyDesk';
import { Dossier } from './views/Dossier';

export interface Scenario {
  id: string;
  label: string;
  clinicalLabel: string;
  bundle: ArtifactBundle;
}

export const SCENARIOS: readonly Scenario[] = [
  {
    id: 'golden',
    label: 'Audited replay fixture',
    clinicalLabel: 'Re-evaluation completed — audited replay',
    bundle: goldenBundle as unknown as ArtifactBundle,
  },
  {
    id: 'fault',
    label: 'Fault fixture: mismatched citation and forbidden tool request',
    clinicalLabel: 'Re-evaluation with citation fault injected',
    bundle: faultBundle as unknown as ArtifactBundle,
  },
  {
    id: 'halted',
    label: 'Fault fixture: ledger integrity unavailable',
    clinicalLabel: 'Re-evaluation during ledger outage',
    bundle: haltedBundle as unknown as ArtifactBundle,
  },
];

function parseRoute(hash: string): string[] {
  return hash.replace(/^#\/?/, '').split('/').filter(Boolean);
}

const NAV = [
  { path: '', label: 'Walkthrough' },
  { path: 'worklist', label: 'Worklist' },
  { path: 'cohort', label: 'Cohort ledger' },
  { path: 'privacy', label: 'Privacy desk' },
  { path: 'dossier', label: 'Evidence dossier' },
] as const;

export function Workbench() {
  const [route, setRoute] = useState<string[]>(() =>
    typeof window === 'undefined' ? [] : parseRoute(window.location.hash),
  );

  useEffect(() => {
    const onHash = () => setRoute(parseRoute(window.location.hash));
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, []);

  const models = useMemo(
    () =>
      Object.fromEntries(
        SCENARIOS.map((scenario) => [scenario.id, buildViewModel(scenario.bundle)]),
      ),
    [],
  );

  const [head, arg] = [route[0] ?? '', route[1] ?? ''];
  let view: React.ReactElement;
  if (head === 'case' && arg === 'hero') {
    view = <HeroCase />;
  } else if (head === 'case' && SCENARIOS.some((s) => s.id === arg)) {
    const scenario = SCENARIOS.find((s) => s.id === arg)!;
    view = <CaseRecord scenario={scenario} result={models[scenario.id]} />;
  } else if (head === 'cohort') {
    view = <CohortLedger />;
  } else if (head === 'privacy') {
    view = <PrivacyDesk />;
  } else if (head === 'dossier') {
    view = <Dossier scenarios={SCENARIOS} models={models} />;
  } else if (head === 'worklist') {
    view = <Worklist scenarios={SCENARIOS} models={models} />;
  } else {
    view = <Walkthrough />;
  }

  const activeNav = head === 'case' ? 'worklist' : head;

  return (
    <StripProvider>
      <div className="workbench">
        <header className="wb-chrome">
          <div className="wb-identity">
            <span className="wb-mark">RECALL</span>
            <span className="wb-app">Clinical Evidence Workbench</span>
          </div>
          <nav className="wb-nav" aria-label="Workbench sections">
            {NAV.map((item) => (
              <a
                key={item.path}
                href={`#/${item.path}`}
                className={activeNav === item.path ? 'wb-nav-item active' : 'wb-nav-item'}
              >
                {item.label}
              </a>
            ))}
          </nav>
          <div className="wb-flags">
            <span className="wb-flag synthetic" title="Every record on this surface is synthetic. No real patient data exists anywhere in the system.">
              SYNTHETIC DATA
            </span>
            <span className="wb-flag draft" title="Night build: cohort ramp and final-cycle figures arrive with the morning bundle regeneration.">
              DRAFT · FINAL BUNDLE PENDING
            </span>
          </div>
        </header>
        <main className="wb-stage">{view}</main>
        <EvidenceStrip />
      </div>
    </StripProvider>
  );
}
