/**
 * Application shell.
 *
 *   #/          the demo page — a white screen and a conversation, which is all
 *               a first-time reader should have to deal with;
 *   #/run       the recorded run, case by case;
 *   #/story     the full narrative and the architecture;
 *   #/demo/...  the evidence surface for the shipped fixtures.
 *
 * Hash routing keeps the build servable from any static host with no rewrite
 * rules, and a route can never select an outcome.
 */

import { useEffect, useState } from 'react';

import { DemoPage } from './demo/DemoPage';
import { RunSurface } from './run/RunSurface';
import { NarrativePage } from './site/NarrativePage';
import { Workbench } from './workbench/Workbench';

function head(hash: string): string {
  return hash.replace(/^#\/?/, '').split('/').filter(Boolean)[0] ?? '';
}

export function App() {
  const [route, setRoute] = useState(() =>
    typeof window === 'undefined' ? '' : head(window.location.hash),
  );

  useEffect(() => {
    const onHash = () => setRoute(head(window.location.hash));
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, []);

  if (route === 'demo') {
    return <Workbench />;
  }
  if (route === 'run') {
    return <RunSurface />;
  }
  if (route === 'story') {
    return <NarrativePage />;
  }
  return <DemoPage />;
}
