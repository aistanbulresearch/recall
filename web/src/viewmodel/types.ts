/** Shared view-model types. Field identifiers come from docs/demo/DERIVED_VALUE_REGISTRY.md. */

export type FieldStatus = 'KNOWN' | 'UNKNOWN' | 'UNAVAILABLE' | 'INCOMPLETE' | 'STALE';

export interface ArtifactWarning {
  code: string;
  message_key: string;
  related_artifact_ids: string[];
}

export interface ArtifactEnvelope {
  schema_name: string;
  schema_version: string;
  artifact_id: string;
  case_id: string | null;
  run_id: string | null;
  producer: { component: string; version: string; identity: string };
  created_at: string;
  input_artifact_ids: string[];
  content_hash: string;
  data_mode: string;
  status: string;
  warnings: ArtifactWarning[];
  extensions: Record<string, unknown>;
  [key: string]: unknown;
}

export interface ArtifactBundle {
  bundle_kind: string;
  bundle_version: string;
  bundle_id: string;
  provenance: Record<string, string>;
  artifacts: ArtifactEnvelope[];
}

export interface SourceRef {
  artifact_id: string;
  artifact_type: string;
  json_path: string;
  content_hash: string;
}

/** One rendered value plus the lineage that produced it. */
export interface ViewField {
  field_id: string;
  label: string;
  value: string | number | null;
  items: ReadonlyArray<unknown>;
  status: FieldStatus;
  source_refs: SourceRef[];
  derived_by: string;
  derived_at: string;
  hidden: boolean;
}

export type ViewModel = Record<string, ViewField>;
