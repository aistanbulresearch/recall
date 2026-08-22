/** Laboratory privacy boundary evidence, derived only from the PrivacyReceipt. */

import type { ViewModel } from '../viewmodel/types';
import { privacyDecisionCopy } from '../viewmodel/semantics';
import { FieldValue, formatValue } from './FieldValue';

export function PrivacyPanel({ model }: { model: ViewModel }) {
  const decision = model['UI-PRIVACY-STATUS'];
  const semantics = privacyDecisionCopy(decision.value);
  return (
    <section className="panel panel-privacy" aria-labelledby="privacy-heading">
      <h2 id="privacy-heading">Laboratory privacy boundary</h2>
      <p className="panel-copy">
        Raw institutional text never leaves the laboratory. Deterministic rules detect identifiers, the local model may
        only propose residual spans, and a deterministic allowlist decides whether the minimised payload may be released.
      </p>
      <p
        className={`decision severity-${decision.status === 'KNOWN' ? semantics.severity : 'unknown'}`}
        data-privacy-decision={decision.status === 'KNOWN' ? String(decision.value) : decision.status}
      >
        <strong>{formatValue(decision)}</strong> — {decision.status === 'KNOWN' ? semantics.plain : 'No privacy receipt resolved.'}
      </p>
      <div className="field-grid">
        <FieldValue field={model['UI-PRIVACY-DETERMINISTIC-SPANS']} />
        <FieldValue field={model['UI-PRIVACY-GEMMA-SPANS']} hint="Approved after deterministic adjudication, not raw model output." />
        <FieldValue field={model['UI-PRIVACY-OUTBOUND-FIELDS']} />
        <FieldValue field={model['UI-PRIVACY-RAW-TEXT-EGRESS']} hint="Acceptance requires zero." />
      </div>
    </section>
  );
}
