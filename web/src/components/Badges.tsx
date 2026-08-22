/** Data-mode and terminal-state badges. Colour is always redundant with text. */

import type { ViewField } from '../viewmodel/types';
import { policyOutcomeCopy, runStateCopy, statusCopy } from '../viewmodel/semantics';
import { formatValue } from './FieldValue';

export function DataModeBadge({ field }: { field: ViewField }) {
  const modes = field.items.map((mode) => String(mode));
  return (
    <span className="badge badge-mode" data-field-id={field.field_id} data-status={field.status}>
      <strong>{field.status === 'KNOWN' ? modes.join(' + ') : statusCopy(field.status).plain}</strong>
      <span className="badge-detail">{formatValue(field)}</span>
    </span>
  );
}

/**
 * Technical `HALTED` and semantic `ABSTAIN` are different states and must never
 * share a visual treatment. The run state carries its own copy and severity.
 */
export function RunStateBadge({ field }: { field: ViewField }) {
  const semantics = runStateCopy(field.value);
  return (
    <span
      className={`badge badge-state severity-${field.status === 'KNOWN' ? semantics.severity : 'unknown'}`}
      data-field-id={field.field_id}
      data-status={field.status}
      data-run-state={field.status === 'KNOWN' ? String(field.value) : field.status}
    >
      <strong>{formatValue(field)}</strong>
      <span className="badge-detail">{field.status === 'KNOWN' ? semantics.plain : statusCopy(field.status).plain}</span>
    </span>
  );
}

export function PolicyOutcomeBadge({ field }: { field: ViewField }) {
  const semantics = policyOutcomeCopy(field.value);
  return (
    <span
      className={`badge badge-outcome severity-${field.status === 'KNOWN' ? semantics.severity : 'unknown'}`}
      data-field-id={field.field_id}
      data-status={field.status}
      data-outcome={field.status === 'KNOWN' ? String(field.value) : field.status}
    >
      <strong>{formatValue(field)}</strong>
      <span className="badge-detail">{field.status === 'KNOWN' ? semantics.plain : statusCopy(field.status).plain}</span>
    </span>
  );
}
