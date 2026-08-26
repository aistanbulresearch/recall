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
  /*
   * 2.0.0 counts by IDENTITY, not by tally: the day's work is carried as lists
   * of case and run ids, so the figure on screen is the length of a list a
   * reader can expand. delta.cases_watched and delta.runs_created do not exist
   * in this contract and are not reconstructed from anything else.
   */
  {
    fieldId: 'UI-COHORT-CASES-DELTA',
    label: 'Cases selected today',
    group: 'cohort',
    artifactType: 'CohortDayManifest',
    jsonPath: '$.delta.selected_case_ids',
    derivation: { kind: 'count' },
    missingStatus: 'UNKNOWN',
    goldenPath: false,
    hideWhenMissing: true,
  },
  {
    // newly_created, not authoritative: authoritative_run_ids is the union of
    // newly created and REUSED, so counting it would report reused runs as
    // today's work.
    fieldId: 'UI-COHORT-RUNS-DELTA',
    label: 'Runs created today',
    group: 'cohort',
    artifactType: 'CohortDayManifest',
    jsonPath: '$.delta.newly_created_run_ids',
    derivation: { kind: 'count' },
    missingStatus: 'UNKNOWN',
    goldenPath: false,
    hideWhenMissing: true,
  },
  {
    // Cumulative CASES watched has no field in 2.0.0 and cannot be derived from
    // the manifest: it would need the union of selected_case_ids across every
    // day, which a single day's manifest does not carry. Rather than invent it,
    // the running total shown is the one the contract actually supports.
    fieldId: 'UI-COHORT-CYCLES-TOTAL',
    label: 'Daily cycles to date',
    group: 'cohort',
    artifactType: 'CohortDayManifest',
    jsonPath: '$.cumulative.daily_cycles',
    derivation: { kind: 'exact' },
    missingStatus: 'UNKNOWN',
    goldenPath: false,
    hideWhenMissing: true,
  },
  {
    // The producer's own count of distinct execution dates, derived by it from
    // execution_history. The panel derives the same figure independently, so the
    // two can be compared instead of trusted.
    fieldId: 'UI-COHORT-DISTINCT-DATES',
    label: 'Distinct execution dates',
    group: 'cohort',
    artifactType: 'CohortDayManifest',
    jsonPath: '$.cumulative.distinct_execution_dates',
    derivation: { kind: 'exact' },
    missingStatus: 'UNKNOWN',
    goldenPath: false,
    hideWhenMissing: true,
  },
  {
    // Which code produced this evidence. The example manifest carries a
    // deterministic synthetic sentinel that the contract README says must never
    // be cited as runtime evidence, so this value travels beside the artifact's
    // data_mode exactly as the resolution-mode badge does.
    fieldId: 'UI-COHORT-IMAGE-DIGEST',
    label: 'Image digest',
    group: 'cohort',
    artifactType: 'CohortDayManifest',
    jsonPath: '$.image_digest',
    derivation: { kind: 'exact' },
    missingStatus: 'UNKNOWN',
    goldenPath: false,
    hideWhenMissing: true,
  },
  {
    fieldId: 'UI-COHORT-SOURCE-COMMIT',
    label: 'Source commit',
    group: 'cohort',
    artifactType: 'CohortDayManifest',
    jsonPath: '$.source_commit',
    derivation: { kind: 'exact' },
    missingStatus: 'UNKNOWN',
    goldenPath: false,
    hideWhenMissing: true,
  },
  {
    // 3.0.0: the declared schedule mode. The compressed-session label renders
    // from THIS field or not at all; copy typed into a component is forbidden.
    fieldId: 'UI-COHORT-SCHEDULE-MODE',
    label: 'Schedule mode',
    group: 'cohort',
    artifactType: 'CohortDayManifest',
    jsonPath: '$.schedule_mode',
    derivation: { kind: 'exact' },
    missingStatus: 'UNKNOWN',
    goldenPath: false,
    hideWhenMissing: true,
  },
  {
    // 3.0.0: which compressed cycle this manifest reports.
    fieldId: 'UI-COHORT-CYCLE-ID',
    label: 'Cycle',
    group: 'cohort',
    artifactType: 'CohortDayManifest',
    jsonPath: '$.cycle_id',
    derivation: { kind: 'exact' },
    missingStatus: 'UNKNOWN',
    goldenPath: false,
    hideWhenMissing: true,
  },
  {
    // 3.0.0: hash of the pre-committed prediction plan; the chain from every
    // cycle's counters back to the plan that predicted them.
    fieldId: 'UI-COHORT-PLAN-SHA256',
    label: 'Prediction plan',
    group: 'cohort',
    artifactType: 'CohortDayManifest',
    jsonPath: '$.plan_sha256',
    derivation: { kind: 'exact' },
    missingStatus: 'UNKNOWN',
    goldenPath: false,
    hideWhenMissing: true,
  },
  {
    // 3.0.0 rename of cumulative.daily_cycles; only compressed rows count.
    fieldId: 'UI-COHORT-COMPRESSED-TOTAL',
    label: 'Compressed cycles completed',
    group: 'cohort',
    artifactType: 'CohortDayManifest',
    jsonPath: '$.cumulative.compressed_cycles_completed',
    derivation: { kind: 'exact' },
    missingStatus: 'UNKNOWN',
    goldenPath: false,
    hideWhenMissing: true,
  },
  {
    // The manifest's own declared data mode, so a synthetic sentinel digest can
    // never read as a deployed one.
    fieldId: 'UI-COHORT-DATA-MODE',
    label: 'Manifest data mode',
    group: 'cohort',
    artifactType: 'CohortDayManifest',
    jsonPath: '$.data_mode',
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
