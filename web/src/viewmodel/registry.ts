/**
 * Field registry.
 *
 * Every entry mirrors one row of `docs/demo/DERIVED_VALUE_REGISTRY.md`: the same
 * field identifier, the same source artifact and JSON path, the same
 * deterministic rule, and the same missing behaviour. No field identifier is
 * invented here, and a value can never come from a fixture name or a preset.
 */

import type { FieldStatus } from './types';

export type FieldGroup =
  | 'global'
  | 'cloud'
  | 'watch'
  | 'cohort'
  | 'privacy'
  | 'fleet'
  | 'evidence'
  | 'citation'
  | 'policy'
  | 'task';

export type Derivation =
  | { kind: 'exact' }
  | { kind: 'count' }
  | { kind: 'countArtifacts' }
  | { kind: 'countWhere'; property: string; equals: string }
  | { kind: 'list' }
  | { kind: 'record'; valueProperty: string; properties: readonly string[] }
  | { kind: 'collect'; orderBy?: string }
  | { kind: 'composition'; secondPath: string };

export interface FieldSpec {
  fieldId: string;
  label: string;
  group: FieldGroup;
  artifactType: string;
  jsonPath: string;
  derivation: Derivation;
  missingStatus: FieldStatus;
  goldenPath: boolean;
  /** Registry rule: hide the panel rather than fabricate a pass. */
  hideWhenMissing?: boolean;
  /**
   * An empty collection may render as zero only when this guard path resolves.
   * The contract states that an empty backlog is meaningful only after a
   * verified transition explicitly cleared it; missing is not zero.
   */
  zeroRequiresGuard?: string;
}

export const FIELD_SPECS: readonly FieldSpec[] = [
  {
    fieldId: 'UI-GLOBAL-MODE',
    label: 'Data provenance',
    group: 'global',
    artifactType: 'DataModeReceipt',
    jsonPath: '$.mode_set[*]',
    derivation: { kind: 'composition', secondPath: '$.declared_composition' },
    missingStatus: 'UNKNOWN',
    goldenPath: true,
  },
  {
    fieldId: 'UI-GLOBAL-RUN-ID',
    label: 'Run',
    group: 'global',
    artifactType: 'ScanRun',
    jsonPath: '$.run_id',
    derivation: { kind: 'exact' },
    missingStatus: 'UNKNOWN',
    goldenPath: true,
  },
  {
    fieldId: 'UI-GLOBAL-RUN-STATE',
    label: 'Run state',
    group: 'global',
    artifactType: 'ScanRun',
    jsonPath: '$.state',
    derivation: { kind: 'exact' },
    missingStatus: 'UNKNOWN',
    goldenPath: true,
  },
  {
    fieldId: 'UI-GLOBAL-TRACE-ID',
    label: 'Trace',
    group: 'global',
    artifactType: 'ScanRun',
    jsonPath: '$.trace_id',
    derivation: { kind: 'exact' },
    missingStatus: 'UNAVAILABLE',
    goldenPath: true,
  },
  {
    fieldId: 'UI-GLOBAL-UPDATED',
    label: 'Updated',
    group: 'global',
    artifactType: '*',
    jsonPath: '$.created_at',
    derivation: { kind: 'exact' },
    missingStatus: 'UNKNOWN',
    goldenPath: false,
  },
  {
    fieldId: 'UI-CLOUD-RUNTIME-REV',
    label: 'Cloud revision',
    group: 'cloud',
    artifactType: 'DeploymentReceipt',
    jsonPath: '$.runtime.revision',
    derivation: { kind: 'exact' },
    missingStatus: 'UNAVAILABLE',
    goldenPath: false,
  },
  {
    // resolution_mode lives on RegistryResolutionReceipt. It is deliberately NOT
    // read off RoutingPlan: nothing produces a RoutingPlan, so a badge sourced
    // there would be permanently UNKNOWN.
    //
    // The value is NOT evidence of a resolution having happened. No production
    // path emits this receipt today: the only emitter is a fixture that carries
    // "PINNED_FALLBACK" as a string constant on a SYNTHETIC artifact with no
    // bindings. UI-CLOUD-RESOLUTION-SOURCE therefore travels beside it so a
    // viewer always sees which kind of source produced the value.
    fieldId: 'UI-CLOUD-RESOLUTION-MODE',
    label: 'How the agents were resolved',
    group: 'fleet',
    artifactType: 'RegistryResolutionReceipt',
    jsonPath: '$.resolution_mode',
    derivation: { kind: 'exact' },
    missingStatus: 'UNKNOWN',
    goldenPath: false,
  },
  {
    // The data mode of the artifact the resolution mode came from. A fixture
    // constant must never read as a live fact, so the badge shows its own
    // provenance rather than relying on the reader to know.
    fieldId: 'UI-CLOUD-RESOLUTION-SOURCE',
    label: 'Resolution source',
    group: 'fleet',
    artifactType: 'RegistryResolutionReceipt',
    jsonPath: '$.data_mode',
    derivation: { kind: 'exact' },
    missingStatus: 'UNKNOWN',
    goldenPath: false,
  },
  {
    fieldId: 'UI-CLOUD-REGISTRY-COUNT',
    label: 'Bound agents',
    group: 'cloud',
    artifactType: 'RegistryResolutionReceipt',
    jsonPath: '$.bindings[*]',
    derivation: { kind: 'count' },
    missingStatus: 'INCOMPLETE',
    goldenPath: false,
  },
  {
    fieldId: 'UI-CLOUD-TRANSITIONS',
    label: 'Persisted transitions',
    group: 'cloud',
    artifactType: 'ScanRunEvent',
    jsonPath: '$.event_id',
    derivation: { kind: 'countArtifacts' },
    missingStatus: 'UNKNOWN',
    goldenPath: false,
  },
  {
    fieldId: 'UI-CLOUD-HEALTH',
    label: 'Managed path',
    group: 'cloud',
    artifactType: 'ManagedPathReceipt',
    jsonPath: '$.managed_status',
    derivation: { kind: 'exact' },
    missingStatus: 'UNAVAILABLE',
    goldenPath: false,
  },
  {
    fieldId: 'UI-WATCH-STATUS',
    label: 'Watch status',
    group: 'watch',
    artifactType: 'WatchCase',
    jsonPath: '$.state',
    derivation: { kind: 'exact' },
    missingStatus: 'UNKNOWN',
    goldenPath: true,
  },
  {
    fieldId: 'UI-WATCH-LAST-SCAN',
    label: 'Last scan',
    group: 'watch',
    artifactType: 'WatchCase',
    jsonPath: '$.last_verified_scan.completed_at',
    derivation: { kind: 'exact' },
    missingStatus: 'UNKNOWN',
    goldenPath: false,
  },
  {
    fieldId: 'UI-WATCH-NEXT-SCAN',
    label: 'Next scan',
    group: 'watch',
    artifactType: 'WatchCase',
    jsonPath: '$.next_scan_at',
    derivation: { kind: 'exact' },
    missingStatus: 'UNKNOWN',
    goldenPath: true,
  },
  {
    fieldId: 'UI-WATCH-SCAN-COUNT',
    label: 'Scans',
    group: 'watch',
    artifactType: 'ScanRun',
    jsonPath: '$.artifact_id',
    derivation: { kind: 'countArtifacts' },
    missingStatus: 'UNKNOWN',
    goldenPath: false,
  },
  {
    fieldId: 'UI-WATCH-PENDING',
    label: 'Pending evidence',
    group: 'watch',
    artifactType: 'WatchCase',
    jsonPath: '$.pending_observation_hashes[*]',
    derivation: { kind: 'count' },
    missingStatus: 'UNKNOWN',
    goldenPath: false,
    zeroRequiresGuard: '$.last_verified_scan.completed_at',
  },
  {
    fieldId: 'UI-WATCH-ATTENTION',
    label: 'Attention',
    group: 'watch',
    artifactType: 'WatchCase',
    jsonPath: '$.attention_marker.reason_codes[*]',
    derivation: { kind: 'list' },
    missingStatus: 'INCOMPLETE',
    goldenPath: false,
    hideWhenMissing: true,
  },
  /*
   * Cohort day manifest.
   *
   * Every figure below is READ from the manifest, never accumulated by this
   * surface: the manifest is the authority on its own totals, and a panel that
   * recomputed them would be asserting a second, competing truth.
   *
   * UI-COHORT-MANIFEST-DAYS exists to make one builder behaviour safe. When a
   * bundle carries more than one CohortDayManifest, buildField resolves scalars
   * from the FIRST match rather than the newest, so a stale day could be shown
   * with no outward sign. That field collects every manifest present, so the
   * panel can detect the ambiguity and refuse instead of displaying a number it
   * cannot attribute to a specific day.
   */
  {
    fieldId: 'UI-COHORT-MANIFEST-DAYS',
    label: 'Manifest days present',
    group: 'cohort',
    artifactType: 'CohortDayManifest',
    jsonPath: '$.day_index',
    derivation: { kind: 'collect' },
    missingStatus: 'UNKNOWN',
    goldenPath: false,
    hideWhenMissing: true,
  },
  {
    fieldId: 'UI-COHORT-DAY-INDEX',
    label: 'Day',
    group: 'cohort',
    artifactType: 'CohortDayManifest',
    jsonPath: '$.day_index',
    derivation: { kind: 'exact' },
    missingStatus: 'UNKNOWN',
    goldenPath: false,
    hideWhenMissing: true,
  },
  {
    fieldId: 'UI-COHORT-CASES-DELTA',
    label: 'Cases watched today',
    group: 'cohort',
    artifactType: 'CohortDayManifest',
    jsonPath: '$.delta.cases_watched',
    derivation: { kind: 'exact' },
    missingStatus: 'UNKNOWN',
    goldenPath: false,
    hideWhenMissing: true,
  },
  {
    fieldId: 'UI-COHORT-RUNS-DELTA',
    label: 'Runs created today',
    group: 'cohort',
    artifactType: 'CohortDayManifest',
    jsonPath: '$.delta.runs_created',
    derivation: { kind: 'exact' },
    missingStatus: 'UNKNOWN',
    goldenPath: false,
    hideWhenMissing: true,
  },
  {
    fieldId: 'UI-COHORT-CASES-TOTAL',
    label: 'Cases watched to date',
    group: 'cohort',
    artifactType: 'CohortDayManifest',
    jsonPath: '$.cumulative.cases_watched',
    derivation: { kind: 'exact' },
    missingStatus: 'UNKNOWN',
    goldenPath: false,
    hideWhenMissing: true,
  },
  {
    fieldId: 'UI-COHORT-RUNS-TOTAL',
    label: 'Runs created to date',
    group: 'cohort',
    artifactType: 'CohortDayManifest',
    jsonPath: '$.cumulative.runs_created',
    derivation: { kind: 'exact' },
    missingStatus: 'UNKNOWN',
    goldenPath: false,
    hideWhenMissing: true,
  },
  {
    // Per case, so a mixed cohort is never described by one bundle-wide badge.
    fieldId: 'UI-COHORT-CASES',
    label: 'Cohort cases',
    group: 'cohort',
    artifactType: 'CohortDayManifest',
    jsonPath: '$.cases[*]',
    derivation: { kind: 'list' },
    missingStatus: 'UNKNOWN',
    goldenPath: false,
    hideWhenMissing: true,
  },
  {
    // One step from a VCV on screen to the capture file and hash it is anchored
    // to. A real accession number displayed without its chain is the failure the
    // 575 finding named.
    fieldId: 'UI-COHORT-VCV-ANCHORS',
    label: 'Capture anchors',
    group: 'cohort',
    artifactType: 'CohortDayManifest',
    jsonPath: '$.vcv_anchors[*]',
    derivation: { kind: 'list' },
    missingStatus: 'UNKNOWN',
    goldenPath: false,
    hideWhenMissing: true,
  },
  {
    // Execution provenance, cumulative in each day's manifest. The elapsed-days
    // sentence is derived from these timestamps and is withheld when they do not
    // prove it. Counters alone cannot distinguish four real days from four runs
    // in one evening.
    fieldId: 'UI-COHORT-EXECUTIONS',
    label: 'Execution history',
    group: 'cohort',
    artifactType: 'CohortDayManifest',
    jsonPath: '$.execution_history[*]',
    derivation: { kind: 'list' },
    missingStatus: 'UNKNOWN',
    goldenPath: false,
    hideWhenMissing: true,
  },
  {
    fieldId: 'UI-PRIVACY-STATUS',
    label: 'Privacy gate',
    group: 'privacy',
    artifactType: 'PrivacyReceipt',
    jsonPath: '$.decision',
    derivation: { kind: 'exact' },
    missingStatus: 'INCOMPLETE',
    goldenPath: false,
  },
  {
    fieldId: 'UI-PRIVACY-DETERMINISTIC-SPANS',
    label: 'Rule detections',
    group: 'privacy',
    artifactType: 'PrivacyReceipt',
    jsonPath: '$.detectors.deterministic.approved_spans[*]',
    derivation: { kind: 'count' },
    missingStatus: 'UNKNOWN',
    goldenPath: false,
  },
  {
    fieldId: 'UI-PRIVACY-GEMMA-SPANS',
    label: 'Local model residuals',
    group: 'privacy',
    artifactType: 'PrivacyReceipt',
    jsonPath: '$.detectors.gemma.approved_residual_spans[*]',
    derivation: { kind: 'count' },
    missingStatus: 'UNAVAILABLE',
    goldenPath: false,
  },
  {
    fieldId: 'UI-PRIVACY-OUTBOUND-FIELDS',
    label: 'Cloud fields',
    group: 'privacy',
    artifactType: 'PrivacyReceipt',
    jsonPath: '$.outbound.allowed_field_paths[*]',
    derivation: { kind: 'count' },
    missingStatus: 'INCOMPLETE',
    goldenPath: false,
  },
  {
    fieldId: 'UI-PRIVACY-RAW-TEXT-EGRESS',
    label: 'Raw text sent',
    group: 'privacy',
    artifactType: 'PrivacyReceipt',
    jsonPath: '$.outbound.raw_text_field_count',
    derivation: { kind: 'exact' },
    missingStatus: 'UNKNOWN',
    goldenPath: false,
  },
  {
    fieldId: 'UI-PRIVACY-EGRESS-PROFILE',
    label: 'Egress profile',
    group: 'privacy',
    artifactType: 'PrivacyReceipt',
    jsonPath: '$.detector_versions.egress_profile',
    derivation: { kind: 'exact' },
    missingStatus: 'UNKNOWN',
    goldenPath: false,
  },
  {
    fieldId: 'UI-AGENT-ROSTER',
    label: 'Agent lanes',
    group: 'fleet',
    artifactType: 'RegistryResolutionReceipt',
    jsonPath: '$.bindings[*]',
    derivation: { kind: 'list' },
    missingStatus: 'INCOMPLETE',
    goldenPath: false,
  },
  {
    fieldId: 'UI-AGENT-STATE',
    label: 'Agent state',
    group: 'fleet',
    artifactType: 'ScanRunEvent',
    jsonPath: '$.to_state',
    derivation: { kind: 'collect', orderBy: 'sequence' },
    missingStatus: 'UNKNOWN',
    goldenPath: false,
  },
  {
    fieldId: 'UI-ROUTE-STATUS',
    label: 'Route',
    group: 'fleet',
    artifactType: 'RoutingPlan',
    jsonPath: '$.validation_status',
    derivation: { kind: 'exact' },
    missingStatus: 'INCOMPLETE',
    goldenPath: false,
  },
  {
    fieldId: 'UI-TOOL-DENIAL',
    label: 'Blocked action',
    group: 'fleet',
    artifactType: 'ToolAuthorizationReceipt',
    jsonPath: '$',
    derivation: {
      kind: 'record',
      valueProperty: 'decision',
      properties: ['agent_role', 'tool_id', 'requested_action', 'decision', 'reason_codes'],
    },
    missingStatus: 'UNAVAILABLE',
    goldenPath: false,
    hideWhenMissing: true,
  },
  {
    fieldId: 'UI-EVIDENCE-CANDIDATE',
    label: 'Candidate state',
    group: 'evidence',
    artifactType: 'CandidateDeltaReceipt',
    jsonPath: '$.candidate_delta_state',
    derivation: { kind: 'exact' },
    missingStatus: 'UNKNOWN',
    goldenPath: true,
  },
  {
    fieldId: 'UI-EVIDENCE-CLASS-UNCHANGED',
    label: 'Classification snapshot',
    group: 'evidence',
    artifactType: 'EvidenceDelta',
    jsonPath: '$.comparison.classification_changed',
    derivation: { kind: 'exact' },
    missingStatus: 'UNKNOWN',
    goldenPath: false,
  },
  {
    fieldId: 'UI-CITATION-TOTAL',
    label: 'Material claims',
    group: 'citation',
    artifactType: 'CitationAuditReceipt',
    jsonPath: '$.claim_verdicts[*]',
    derivation: { kind: 'count' },
    missingStatus: 'UNKNOWN',
    goldenPath: false,
  },
  {
    fieldId: 'UI-CITATION-VERIFIED',
    label: 'Verified claims',
    group: 'citation',
    artifactType: 'CitationAuditReceipt',
    jsonPath: '$.claim_verdicts[*]',
    derivation: { kind: 'countWhere', property: 'verdict', equals: 'VERIFIED' },
    missingStatus: 'UNKNOWN',
    goldenPath: true,
  },
  {
    fieldId: 'UI-CITATION-STATUS',
    label: 'Independent audit',
    group: 'citation',
    artifactType: 'CitationAuditReceipt',
    jsonPath: '$.audit_status',
    derivation: { kind: 'exact' },
    missingStatus: 'INCOMPLETE',
    goldenPath: true,
  },
  {
    fieldId: 'UI-POLICY-OUTCOME',
    label: 'Outcome',
    group: 'policy',
    artifactType: 'PolicyDecision',
    jsonPath: '$.outcome',
    derivation: { kind: 'exact' },
    missingStatus: 'INCOMPLETE',
    goldenPath: true,
  },
  {
    fieldId: 'UI-POLICY-REASONS',
    label: 'Why',
    group: 'policy',
    artifactType: 'PolicyDecision',
    jsonPath: '$.reason_codes[*]',
    derivation: { kind: 'list' },
    missingStatus: 'UNKNOWN',
    goldenPath: true,
  },
  {
    fieldId: 'UI-POLICY-MISSING',
    label: 'Missing proof',
    group: 'policy',
    artifactType: 'PolicyDecision',
    jsonPath: '$.missing_prerequisites[*]',
    derivation: { kind: 'list' },
    missingStatus: 'UNKNOWN',
    goldenPath: false,
  },
  {
    fieldId: 'UI-TASK-COUNT-RUN',
    label: 'Simulated tasks from run',
    group: 'task',
    artifactType: 'ReviewTask',
    jsonPath: '$.artifact_id',
    derivation: { kind: 'countArtifacts' },
    missingStatus: 'UNKNOWN',
    goldenPath: true,
  },
  {
    fieldId: 'UI-TASK-STATE',
    label: 'Task state',
    group: 'task',
    artifactType: 'ReviewTask',
    jsonPath: '$.state',
    derivation: { kind: 'exact' },
    missingStatus: 'UNKNOWN',
    goldenPath: false,
    hideWhenMissing: true,
  },
];

export const GOLDEN_PATH_FIELD_IDS: readonly string[] = FIELD_SPECS.filter((spec) => spec.goldenPath).map(
  (spec) => spec.fieldId,
);
