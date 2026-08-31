/**
 * Registered static copy for fixed policy and lifecycle semantics.
 *
 * The information architecture allows static copy that explains roles,
 * limitations, and fixed semantics. It forbids static copy that carries a
 * run-specific fact. Every entry here is a stable definition, and no entry may
 * be selected by a fixture name: components look up the value that the view
 * model derived from an artifact.
 */

export type Severity = 'neutral' | 'positive' | 'caution' | 'blocked' | 'unknown';

export interface SemanticEntry {
  plain: string;
  severity: Severity;
}

const POLICY_OUTCOMES: Record<string, SemanticEntry> = {
  REVIEW_REQUIRED: { plain: 'A specialist review was allowed for this case.', severity: 'positive' },
  ABSTAIN: { plain: 'Recall stopped because required proof was incomplete.', severity: 'caution' },
  NO_ACTION: { plain: 'Nothing changed enough to involve a specialist.', severity: 'neutral' },
};

const RUN_STATES: Record<string, SemanticEntry> = {
  CREATED: { plain: 'Run recorded.', severity: 'neutral' },
  QUEUED: { plain: 'Run published to the work queue.', severity: 'neutral' },
  ROUTING: { plain: 'Resolving which registered agents may take part.', severity: 'neutral' },
  WATCHING: { plain: 'Reading approved public sources.', severity: 'neutral' },
  ASSESSING: { plain: 'Comparing the previous and current evidence snapshots.', severity: 'neutral' },
  AUDITING: { plain: 'A second agent independently reopened every source.', severity: 'neutral' },
  POLICY_EVALUATION: { plain: 'Deterministic policy is evaluating the recorded facts.', severity: 'neutral' },
  REVIEW_REQUIRED: { plain: 'A specialist review was allowed for this case.', severity: 'positive' },
  ABSTAIN: { plain: 'Recall stopped because required proof was incomplete.', severity: 'caution' },
  NO_ACTION: { plain: 'Nothing changed enough to involve a specialist.', severity: 'neutral' },
  HALTED: { plain: 'Execution stopped for a technical reason. This is not a policy outcome.', severity: 'blocked' },
};

const PRIVACY_DECISIONS: Record<string, SemanticEntry> = {
  ACCEPTED: { plain: 'The minimised payload was allowed to leave the laboratory.', severity: 'positive' },
  QUARANTINED: { plain: 'The payload stayed in the laboratory.', severity: 'blocked' },
};

const AUTHORIZATION_DECISIONS: Record<string, SemanticEntry> = {
  DENIED: { plain: 'The action was refused before it could run.', severity: 'blocked' },
  ALLOWED: { plain: 'The action was inside the agent tool scope.', severity: 'neutral' },
};

const STATUS_COPY: Record<string, SemanticEntry> = {
  KNOWN: { plain: 'Derived from an authoritative artifact.', severity: 'neutral' },
  UNKNOWN: { plain: 'No authoritative source resolved. This is not zero.', severity: 'unknown' },
  UNAVAILABLE: { plain: 'The required source was not available. No claim is made.', severity: 'unknown' },
  INCOMPLETE: { plain: 'A required part is missing, so the value is not usable.', severity: 'caution' },
  STALE: { plain: 'The newest artifact is older than the freshness window.', severity: 'caution' },
};

const REASON_CODE_COPY: Record<string, string> = {
  all_prerequisites_verified: 'Every required proof was present and verified.',
  material_change_candidate_present: 'A deterministic comparison found a candidate change.',
  citation_audit_incomplete: 'The independent citation audit did not complete.',
  material_claim_rejected: 'A material claim failed independent verification.',
  tool_authorization_incomplete: 'A required tool authorisation was not granted.',
  tool_not_allowlisted: 'The requested tool is not in this role tool scope.',
  role_cannot_create_terminal_outcome: 'This role may never create a terminal outcome.',
  refetched_title_mismatch: 'The independently refetched record did not match the cited title.',
  metadata_matched: 'The independently refetched metadata matched the claim.',
  ledger_unavailable: 'The authoritative ledger could not be reached.',
  ledger_integrity_unavailable: 'Ledger integrity could not be established.',
  snapshot_incomplete: 'The evidence snapshot was incomplete.',
};

const UNKNOWN_ENTRY: SemanticEntry = {
  plain: 'Unregistered value. Recall does not invent an explanation.',
  severity: 'unknown',
};

export function policyOutcomeCopy(value: string | number | null): SemanticEntry {
  return lookup(POLICY_OUTCOMES, value);
}

export function runStateCopy(value: string | number | null): SemanticEntry {
  return lookup(RUN_STATES, value);
}

export function privacyDecisionCopy(value: string | number | null): SemanticEntry {
  return lookup(PRIVACY_DECISIONS, value);
}

const RESOLUTION_MODES: Record<string, SemanticEntry> = {
  REGISTRY: {
    plain: 'Resolved from the live agent registry.',
    severity: 'neutral',
  },
  MANUAL_SERVICE: {
    plain: 'Resolved from a manually registered service entry, not registry discovery.',
    severity: 'caution',
  },
  PINNED_FALLBACK: {
    plain: 'Resolved from a pinned manifest because registry discovery was unavailable.',
    severity: 'caution',
  },
};

export function resolutionModeCopy(value: string | number | null): SemanticEntry {
  return lookup(RESOLUTION_MODES, value);
}

/**
 * What kind of source the resolution mode came from.
 *
 * No production path emits a RegistryResolutionReceipt today. The only emitter
 * is a fixture carrying a string constant on a SYNTHETIC artifact with no
 * bindings, so the mode reports what the fixture was written to say rather than
 * what any resolver did. The badge states that rather than leaving a reader to
 * assume a measurement.
 */
export function resolutionSourceCopy(dataMode: string | number | null): SemanticEntry {
  if (dataMode === 'SYNTHETIC' || dataMode === 'MOCK') {
    return {
      plain: 'Declared by a fixture, not observed from a live resolution.',
      severity: 'caution',
    };
  }
  if (dataMode === null) {
    return UNKNOWN_ENTRY;
  }
  return { plain: 'Observed from a live resolution.', severity: 'neutral' };
}

/**
 * One sentence naming who was refused, what they asked for, and why.
 *
 * The comprehension gate asks whether a first-time viewer understands what was
 * refused and why. A DENIED headline alone answers neither: it reports that a
 * refusal happened and leaves the tool and the reason in a definition list
 * nobody reads at speed. Every part of this sentence is a field of the receipt,
 * so the label is a view of the artifact and never a caption typed over it.
 */
export function denialHeadline(properties: Record<string, unknown>): string | null {
  const role = properties.agent_role;
  const tool = properties.tool_id;
  const action = properties.requested_action;
  if (typeof role !== 'string' || typeof tool !== 'string') {
    return null;
  }
  const actor = role.toLowerCase().replace(/_/g, ' ');
  const codes = Array.isArray(properties.reason_codes) ? properties.reason_codes : [];
  const first = codes.find((code): code is string => typeof code === 'string');
  const because = first ? reasonCodeCopy(first) : null;
  const asked = typeof action === 'string' ? `${tool} for ${action.replace(/_/g, ' ')}` : tool;
  return because
    ? `The ${actor} was refused ${asked}. ${because}`
    : `The ${actor} was refused ${asked}.`;
}

export function authorizationCopy(value: string | number | null): SemanticEntry {
  return lookup(AUTHORIZATION_DECISIONS, value);
}

export function statusCopy(value: string): SemanticEntry {
  return lookup(STATUS_COPY, value);
}

export function reasonCodeCopy(code: string): string {
  return REASON_CODE_COPY[code] ?? 'Unregistered reason code. Shown verbatim without interpretation.';
}

function lookup(table: Record<string, SemanticEntry>, value: string | number | null): SemanticEntry {
  if (value === null) {
    return UNKNOWN_ENTRY;
  }
  return table[String(value)] ?? UNKNOWN_ENTRY;
}
