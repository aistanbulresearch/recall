/**
 * Deterministic View Model Builder.
 *
 * Rules enforced here:
 *  - a value exists only when an authoritative artifact resolved it;
 *  - a missing source produces the registered missing status, never zero,
 *    never a clean or safe default;
 *  - every value carries its source lineage;
 *  - the bundle identifier is never an input to any value.
 */

import { resolvePath } from './jsonpath';
import { FIELD_SPECS, type FieldSpec } from './registry';
import type { ArtifactBundle, ArtifactEnvelope, SourceRef, ViewField, ViewModel } from './types';

export const VIEW_MODEL_BUILDER_VERSION = 'view-model-builder@1.0.0';
export const DEFAULT_FRESHNESS_WINDOW_MS = 15 * 60 * 1000;

const REQUIRED_ENVELOPE_FIELDS = [
  'schema_name',
  'schema_version',
  'artifact_id',
  'case_id',
  'run_id',
  'producer',
  'created_at',
  'input_artifact_ids',
  'content_hash',
  'data_mode',
  'status',
  'warnings',
  'extensions',
] as const;

/** Contract versions this surface knows how to read. */
export const SUPPORTED_SCHEMA_VERSIONS: Record<string, readonly string[]> = {
  PrivacyReceipt: ['1.0.0'],
  WatchCase: ['2.0.0'],
  ScanRun: ['1.0.0'],
  ScanRunEvent: ['1.0.0'],
  RoutingPlan: ['1.0.0'],
  RegistryResolutionReceipt: ['1.0.0'],
  ToolAuthorizationReceipt: ['1.0.0'],
  EvidenceSnapshot: ['1.0.0'],
  CandidateDeltaReceipt: ['1.0.0'],
  EvidenceDelta: ['2.0.0'],
  CitationAuditReceipt: ['1.0.0'],
  DataModeReceipt: ['2.0.0'],
  PolicyDecision: ['2.0.0'],
  ReviewTask: ['1.0.0'],
  FailureReceipt: ['1.0.0'],
  DeploymentReceipt: ['1.0.0'],
  ManagedPathReceipt: ['1.0.0'],
  // Cohort day manifest. Both versions, mirroring the producer's own schema
  // map, which keeps 2.0.0 as a legacy read beside 2.1.0: day-2 was emitted as
  // 2.0.0 and day-3 onward emits 2.1.0. 1.0.0 stays out; nothing ever emitted
  // it. Each day's bundle carries ONE manifest in one version, so a mixed
  // history never occurs inside an artifact: the version split is across days,
  // which this surface never stitches (one-manifest-per-bundle rule).
  CohortDayManifest: ['2.0.0', '2.1.0'],
  // The typed receipt an INCOMPLETE 2.1.0 history row references.
  CohortDayFailureReceipt: ['1.0.0'],
};

export interface RejectedArtifact {
  artifact_id: string;
  schema_name: string;
  reason_code: string;
}

export interface BuildOptions {
  /** Injected so tests and rendering stay deterministic. */
  now?: Date;
  freshnessWindowMs?: number;
}

export interface BuildResult {
  fields: ViewModel;
  rejected: RejectedArtifact[];
  acceptedArtifactCount: number;
}

export function validateArtifact(artifact: ArtifactEnvelope): string | null {
  for (const field of REQUIRED_ENVELOPE_FIELDS) {
    if (!Object.prototype.hasOwnProperty.call(artifact, field)) {
      return 'contract_required_field_missing';
    }
  }
  const supported = SUPPORTED_SCHEMA_VERSIONS[artifact.schema_name];
  if (!supported) {
    return 'contract_schema_unregistered';
  }
  if (!supported.includes(artifact.schema_version)) {
    return 'contract_major_unsupported';
  }
  return null;
}

export function buildViewModel(bundle: ArtifactBundle, options: BuildOptions = {}): BuildResult {
  const rejected: RejectedArtifact[] = [];
  const accepted: ArtifactEnvelope[] = [];

  for (const artifact of bundle.artifacts ?? []) {
    const reason = validateArtifact(artifact);
    if (reason) {
      rejected.push({
        artifact_id: String(artifact?.artifact_id ?? 'unknown'),
        schema_name: String(artifact?.schema_name ?? 'unknown'),
        reason_code: reason,
      });
      continue;
    }
    accepted.push(artifact);
  }

  const derivedAt = (options.now ?? new Date()).toISOString();
  const fields: ViewModel = {};
  for (const spec of FIELD_SPECS) {
    fields[spec.fieldId] = buildField(spec, accepted, derivedAt, options);
  }
  return { fields, rejected, acceptedArtifactCount: accepted.length };
}

function missingField(spec: FieldSpec, derivedAt: string): ViewField {
  return {
    field_id: spec.fieldId,
    label: spec.label,
    value: null,
    items: [],
    status: spec.missingStatus,
    source_refs: [],
    derived_by: VIEW_MODEL_BUILDER_VERSION,
    derived_at: derivedAt,
    hidden: Boolean(spec.hideWhenMissing),
  };
}

function sourceRef(artifact: ArtifactEnvelope, jsonPath: string): SourceRef {
  return {
    artifact_id: artifact.artifact_id,
    artifact_type: artifact.schema_name,
    json_path: jsonPath,
    content_hash: artifact.content_hash,
  };
}

function buildField(
  spec: FieldSpec,
  artifacts: ArtifactEnvelope[],
  derivedAt: string,
  options: BuildOptions,
): ViewField {
  if (spec.artifactType === '*') {
    return buildNewestArtifactField(spec, artifacts, derivedAt, options);
  }

  const matching = artifacts.filter((artifact) => artifact.schema_name === spec.artifactType);
  if (matching.length === 0) {
    return missingField(spec, derivedAt);
  }

  if (spec.derivation.kind === 'collect') {
    const orderBy = spec.derivation.orderBy;
    const ordered = orderBy
      ? [...matching].sort((left, right) => Number(left[orderBy] ?? 0) - Number(right[orderBy] ?? 0))
      : matching;
    const items = ordered
      .map((artifact) => resolvePath(artifact, spec.jsonPath))
      .filter((entry) => entry.found)
      .map((entry) => entry.value);
    if (items.length === 0) {
      return missingField(spec, derivedAt);
    }
    return {
      ...missingField(spec, derivedAt),
      value: items.length,
      items,
      status: 'KNOWN',
      source_refs: ordered.map((artifact) => sourceRef(artifact, spec.jsonPath)),
      hidden: false,
    };
  }

  if (spec.derivation.kind === 'countArtifacts') {
    return {
      ...missingField(spec, derivedAt),
      value: matching.length,
      status: 'KNOWN',
      source_refs: matching.map((artifact) => sourceRef(artifact, spec.jsonPath)),
      hidden: false,
    };
  }

  const artifact = matching[0];
  const resolved = resolvePath(artifact, spec.jsonPath);
  if (!resolved.found || resolved.value === null) {
    return missingField(spec, derivedAt);
  }

  const base: ViewField = {
    ...missingField(spec, derivedAt),
    status: 'KNOWN',
    source_refs: [sourceRef(artifact, spec.jsonPath)],
    hidden: false,
  };

  switch (spec.derivation.kind) {
    case 'exact':
      return { ...base, value: renderScalar(resolved.value) };
    case 'count': {
      if (!Array.isArray(resolved.value)) {
        return missingField(spec, derivedAt);
      }
      if (resolved.value.length === 0 && spec.zeroRequiresGuard) {
        const guard = resolvePath(artifact, spec.zeroRequiresGuard);
        if (!guard.found || guard.value === null) {
          return { ...missingField(spec, derivedAt), status: 'INCOMPLETE' };
        }
        return {
          ...base,
          value: 0,
          items: [],
          source_refs: [sourceRef(artifact, spec.jsonPath), sourceRef(artifact, spec.zeroRequiresGuard)],
        };
      }
      return { ...base, value: resolved.value.length, items: resolved.value };
    }
    case 'list': {
      if (!Array.isArray(resolved.value)) {
        return missingField(spec, derivedAt);
      }
      return { ...base, value: resolved.value.length, items: resolved.value };
    }
    case 'countWhere': {
      if (!Array.isArray(resolved.value)) {
        return missingField(spec, derivedAt);
      }
      const { property, equals } = spec.derivation;
      const selected = resolved.value.filter(
        (item) => typeof item === 'object' && item !== null && (item as Record<string, unknown>)[property] === equals,
      );
      return { ...base, value: selected.length, items: selected };
    }
    case 'record': {
      if (typeof resolved.value !== 'object' || resolved.value === null) {
        return missingField(spec, derivedAt);
      }
      const source = resolved.value as Record<string, unknown>;
      const entries = spec.derivation.properties
        .filter((property) => Object.prototype.hasOwnProperty.call(source, property))
        .map((property) => ({ property, value: source[property] }));
      const primary = source[spec.derivation.valueProperty];
      if (primary === undefined || primary === null) {
        return missingField(spec, derivedAt);
      }
      return {
        ...base,
        value: renderScalar(primary),
        items: entries,
        source_refs: entries.map((entry) => sourceRef(artifact, `$.${entry.property}`)),
      };
    }
    case 'composition': {
      const second = resolvePath(artifact, spec.derivation.secondPath);
      if (!Array.isArray(resolved.value) || !second.found) {
        return missingField(spec, derivedAt);
      }
      return {
        ...base,
        value: String(second.value),
        items: resolved.value,
        source_refs: [sourceRef(artifact, spec.jsonPath), sourceRef(artifact, spec.derivation.secondPath)],
      };
    }
    default:
      return missingField(spec, derivedAt);
  }
}

function buildNewestArtifactField(
  spec: FieldSpec,
  artifacts: ArtifactEnvelope[],
  derivedAt: string,
  options: BuildOptions,
): ViewField {
  if (artifacts.length === 0) {
    return missingField(spec, derivedAt);
  }
  const newest = artifacts.reduce((left, right) => (left.created_at >= right.created_at ? left : right));
  const now = options.now;
  const windowMs = options.freshnessWindowMs ?? DEFAULT_FRESHNESS_WINDOW_MS;
  const createdAtMs = Date.parse(newest.created_at);
  const stale = now !== undefined && Number.isFinite(createdAtMs) && now.getTime() - createdAtMs > windowMs;
  return {
    ...missingField(spec, derivedAt),
    value: newest.created_at,
    status: stale ? 'STALE' : 'KNOWN',
    source_refs: [sourceRef(newest, spec.jsonPath)],
    hidden: false,
  };
}

function renderScalar(value: unknown): string | number {
  if (typeof value === 'number' || typeof value === 'string') {
    return value;
  }
  if (typeof value === 'boolean') {
    return String(value);
  }
  return JSON.stringify(value);
}
