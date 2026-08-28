/**
 * Application shell: the Clinical Evidence Workbench.
 *
 * The workbench owns navigation and the evidence substrate strip. The former
 * Mission Control surface lives on as the Evidence Dossier view inside it;
 * the rule it enforced is unchanged everywhere: inputs select bundles,
 * outcomes are always derived.
 */

import { Workbench } from './workbench/Workbench';

export function App() {
  return <Workbench />;
}
