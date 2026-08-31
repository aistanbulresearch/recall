/**
 * Application shell: two surfaces on one static build.
 *
 *   #/           the jury-facing narrative page — a document that explains the
 *                system, its authority boundary and how far each claim is proven;
 *   #/demo/...   the evidence surface — the derived records themselves, the
 *                three-valued outcomes, the cohort ledger and the privacy desk.
 *
 * Hash routing keeps the build servable from any static host with no rewrite
 * rules. A route selects which record is on screen; it can never select an
 * outcome.
 */

import { useEffect, useState } from 'react';

import { NarrativePage } from './site/NarrativePage';
import { Workbench } from './workbench/Workbench';

function isDemoRoute(hash: string): boolean {
  return hash.replace(/^#\/?/, '').split('/').filter(Boolean)[0] === 'demo';
}

export function App() {
  const [demo, setDemo] = useState(() =>
    typeof window === 'undefined' ? false : isDemoRoute(window.location.hash),
  );

  useEffect(() => {
    const onHash = () => setDemo(isDemoRoute(window.location.hash));
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, []);

  return demo ? <Workbench /> : <NarrativePage />;
}
