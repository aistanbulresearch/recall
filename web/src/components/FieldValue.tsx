/**
 * Renders one derived value with its status and lineage.
 *
 * A known value without lineage is a defect, not a display case: the component
 * throws so it cannot reach a screen recording.
 */

import type { ViewField } from '../viewmodel/types';
import { statusCopy } from '../viewmodel/semantics';

export class MissingLineageError extends Error {}

interface FieldValueProps {
  field: ViewField;
  hint?: string;
}

export function formatValue(field: ViewField): string {
  if (field.status !== 'KNOWN' && field.status !== 'STALE') {
    return field.status;
  }
  return field.value === null ? field.status : String(field.value);
}

export function FieldValue({ field, hint }: FieldValueProps) {
  if (field.status === 'KNOWN' && field.source_refs.length === 0) {
    throw new MissingLineageError(`${field.field_id} rendered a value without source lineage`);
  }
  const status = statusCopy(field.status);
  return (
    <div className="field" data-field-id={field.field_id} data-status={field.status}>
      <span className="field-label">{field.label}</span>
      <span className={`field-value severity-${status.severity}`}>{formatValue(field)}</span>
      {hint ? <span className="field-hint">{hint}</span> : null}
      {field.status === 'KNOWN' ? null : <span className="field-status-copy">{status.plain}</span>}
      <details className="lineage">
        <summary>Source</summary>
        {field.source_refs.length === 0 ? (
          <p className="lineage-empty">No authoritative source resolved for this field.</p>
        ) : (
          <ul>
            {field.source_refs.map((reference) => (
              <li key={`${reference.artifact_id}:${reference.json_path}`}>
                <code>{reference.artifact_type}</code> <code>{reference.json_path}</code>
                <br />
                <code className="lineage-id">{reference.artifact_id}</code>
                <br />
                <code className="lineage-hash">{reference.content_hash}</code>
              </li>
            ))}
          </ul>
        )}
        <p className="lineage-derivation">
          derived by <code>{field.derived_by}</code> at <code>{field.derived_at}</code>
        </p>
      </details>
    </div>
  );
}
