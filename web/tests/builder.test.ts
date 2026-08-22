/** View Model Builder: derivation, missing behaviour, and contract rejection. */

import { describe, expect, it } from 'vitest';

import goldenBundle from '../src/bundles/golden.json';
import faultBundle from '../src/bundles/fault.json';
import haltedBundle from '../src/bundles/halted.json';
import { buildViewModel, validateArtifact } from '../src/viewmodel/builder';
import { FIELD_SPECS, GOLDEN_PATH_FIELD_IDS } from '../src/viewmodel/registry';
import type { ArtifactBundle, ArtifactEnvelope } from '../src/viewmodel/types';

const golden = goldenBundle as unknown as ArtifactBundle;
const fault = faultBundle as unknown as ArtifactBundle;
const halted = haltedBundle as unknown as ArtifactBundle;

function clone(bundle: ArtifactBundle): ArtifactBundle {
  return JSON.parse(JSON.stringify(bundle)) as ArtifactBundle;
}

function withoutArtifactType(bundle: ArtifactBundle, schemaName: string): ArtifactBundle {
  const copy = clone(bundle);
  copy.artifacts = copy.artifacts.filter((artifact) => artifact.schema_name !== schemaName);
  return copy;
}

function dropField(artifact: ArtifactEnvelope, name: string): void {
  delete (artifact as Record<string, unknown>)[name];
}

function findArtifact(bundle: ArtifactBundle, schemaName: string): ArtifactEnvelope {
  const artifact = bundle.artifacts.find((entry) => entry.schema_name === schemaName);
  if (!artifact) {
    throw new Error(`fixture is missing ${schemaName}`);
  }
  return artifact;
}

describe('golden path coverage', () => {
  it('registers twelve golden-path fields', () => {
    expect(GOLDEN_PATH_FIELD_IDS).toHaveLength(12);
  });

  it('resolves every golden-path field from the audited fixture', () => {
    const { fields } = buildViewModel(golden);
    for (const fieldId of GOLDEN_PATH_FIELD_IDS) {
      expect(fields[fieldId].status, fieldId).toBe('KNOWN');
      expect(fields[fieldId].source_refs.length, fieldId).toBeGreaterThan(0);
    }
  });

  it('gives every resolved field at least one source reference', () => {
    const { fields } = buildViewModel(golden);
    for (const spec of FIELD_SPECS) {
      const field = fields[spec.fieldId];
      if (field.status === 'KNOWN' || field.status === 'STALE') {
        expect(field.source_refs.length, spec.fieldId).toBeGreaterThan(0);
        for (const reference of field.source_refs) {
          expect(reference.artifact_id).toBeTruthy();
          expect(reference.content_hash).toMatch(/^[0-9a-f]{64}$/);
        }
      }
    }
  });
});

describe('derivations', () => {
  it('counts claim verdicts and verified claims separately', () => {
    const { fields } = buildViewModel(golden);
    const audit = findArtifact(golden, 'CitationAuditReceipt');
    const verdicts = audit.claim_verdicts as Array<{ verdict: string }>;
    expect(fields['UI-CITATION-TOTAL'].value).toBe(verdicts.length);
    expect(fields['UI-CITATION-VERIFIED'].value).toBe(verdicts.filter((v) => v.verdict === 'VERIFIED').length);
  });

  it('counts review tasks from the task ledger, not from the policy outcome', () => {
    const goldenModel = buildViewModel(golden).fields;
    const faultModel = buildViewModel(fault).fields;
    expect(goldenModel['UI-TASK-COUNT-RUN'].value).toBe(1);
    expect(faultModel['UI-TASK-COUNT-RUN'].status).toBe('UNKNOWN');
    expect(faultModel['UI-TASK-COUNT-RUN'].value).toBeNull();
  });

  it('renders the exact data-mode composition rather than one scalar label', () => {
    const { fields } = buildViewModel(golden);
    expect(fields['UI-GLOBAL-MODE'].value).toBe('SYNTHETIC_WITH_CAPTURED_REPLAY');
    expect(fields['UI-GLOBAL-MODE'].items).toEqual(['CAPTURED_REPLAY', 'SYNTHETIC']);
    expect(fields['UI-GLOBAL-MODE'].source_refs).toHaveLength(2);
  });

  it('exposes the denial record fields from the receipt', () => {
    const { fields } = buildViewModel(fault);
    const denial = fields['UI-TOOL-DENIAL'];
    expect(denial.status).toBe('KNOWN');
    expect(denial.value).toBe('DENIED');
    const properties = denial.items.map((entry) => (entry as { property: string }).property);
    expect(properties).toContain('reason_codes');
    expect(properties).toContain('tool_id');
  });

  it('keeps technical HALTED separate from a policy outcome', () => {
    const { fields } = buildViewModel(halted);
    expect(fields['UI-GLOBAL-RUN-STATE'].value).toBe('HALTED');
    expect(fields['UI-POLICY-OUTCOME'].status).toBe('INCOMPLETE');
    expect(fields['UI-POLICY-OUTCOME'].value).toBeNull();
  });
});

describe('missing sources never become clean values', () => {
  it.each([
    ['PrivacyReceipt', 'UI-PRIVACY-STATUS', 'INCOMPLETE'],
    ['PrivacyReceipt', 'UI-PRIVACY-DETERMINISTIC-SPANS', 'UNKNOWN'],
    ['PrivacyReceipt', 'UI-PRIVACY-RAW-TEXT-EGRESS', 'UNKNOWN'],
    ['PrivacyReceipt', 'UI-PRIVACY-EGRESS-PROFILE', 'UNKNOWN'],
    ['CitationAuditReceipt', 'UI-CITATION-STATUS', 'INCOMPLETE'],
    ['CitationAuditReceipt', 'UI-CITATION-VERIFIED', 'UNKNOWN'],
    ['PolicyDecision', 'UI-POLICY-OUTCOME', 'INCOMPLETE'],
    ['ReviewTask', 'UI-TASK-COUNT-RUN', 'UNKNOWN'],
    ['RegistryResolutionReceipt', 'UI-CLOUD-REGISTRY-COUNT', 'INCOMPLETE'],
    ['DeploymentReceipt', 'UI-CLOUD-RUNTIME-REV', 'UNAVAILABLE'],
    ['ManagedPathReceipt', 'UI-CLOUD-HEALTH', 'UNAVAILABLE'],
    ['ScanRunEvent', 'UI-CLOUD-TRANSITIONS', 'UNKNOWN'],
    ['DataModeReceipt', 'UI-GLOBAL-MODE', 'UNKNOWN'],
    ['WatchCase', 'UI-WATCH-STATUS', 'UNKNOWN'],
  ])('removing %s makes %s report %s and never zero', (schemaName, fieldId, expectedStatus) => {
    const { fields } = buildViewModel(withoutArtifactType(golden, schemaName));
    expect(fields[fieldId].status).toBe(expectedStatus);
    expect(fields[fieldId].value).toBeNull();
    expect(fields[fieldId].value).not.toBe(0);
    expect(fields[fieldId].source_refs).toHaveLength(0);
  });

  it('reports UNKNOWN rather than zero when the pending backlog path is absent', () => {
    const copy = clone(golden);
    const watchCase = findArtifact(copy, 'WatchCase');
    dropField(watchCase, 'pending_observation_hashes');
    const { fields } = buildViewModel(copy);
    expect(fields['UI-WATCH-PENDING'].status).toBe('UNKNOWN');
    expect(fields['UI-WATCH-PENDING'].value).toBeNull();
  });
});

describe('empty collections and multi-artifact collection', () => {
  it('renders an empty backlog as zero only when a verified scan cleared it', () => {
    const cleared = buildViewModel(golden).fields['UI-WATCH-PENDING'];
    expect(cleared.status).toBe('KNOWN');
    expect(cleared.value).toBe(0);
    expect(cleared.source_refs).toHaveLength(2);

    const copy = clone(golden);
    (findArtifact(copy, 'WatchCase').last_verified_scan as Record<string, unknown>).completed_at = null;
    const unverified = buildViewModel(copy).fields['UI-WATCH-PENDING'];
    expect(unverified.status).toBe('INCOMPLETE');
    expect(unverified.value).toBeNull();
  });

  it('collects agent states across every persisted event in sequence order', () => {
    const { fields } = buildViewModel(golden);
    const events = golden.artifacts.filter((artifact) => artifact.schema_name === 'ScanRunEvent');
    expect(fields['UI-AGENT-STATE'].status).toBe('KNOWN');
    expect(fields['UI-AGENT-STATE'].items).toHaveLength(events.length);
    expect(fields['UI-AGENT-STATE'].items[0]).toBe('QUEUED');
    expect(fields['UI-AGENT-STATE'].source_refs).toHaveLength(events.length);
  });

  it('reports UNKNOWN agent states when no event artifact exists', () => {
    const { fields } = buildViewModel(withoutArtifactType(golden, 'ScanRunEvent'));
    expect(fields['UI-AGENT-STATE'].status).toBe('UNKNOWN');
    expect(fields['UI-AGENT-STATE'].value).toBeNull();
  });
});

describe('artifact validation', () => {
  it('rejects an unsupported major version', () => {
    const copy = clone(golden);
    findArtifact(copy, 'PolicyDecision').schema_version = '3.0.0';
    const result = buildViewModel(copy);
    expect(result.rejected.map((entry) => entry.reason_code)).toContain('contract_major_unsupported');
    expect(result.fields['UI-POLICY-OUTCOME'].status).toBe('INCOMPLETE');
  });

  it('rejects an artifact missing a required envelope field', () => {
    const copy = clone(golden);
    dropField(findArtifact(copy, 'ScanRun'), 'trace_id');
    dropField(findArtifact(copy, 'WatchCase'), 'content_hash');
    const result = buildViewModel(copy);
    expect(result.rejected.map((entry) => entry.schema_name)).toContain('WatchCase');
    expect(result.fields['UI-WATCH-STATUS'].status).toBe('UNKNOWN');
    expect(result.fields['UI-GLOBAL-TRACE-ID'].status).toBe('UNAVAILABLE');
  });

  it('rejects an unregistered schema name', () => {
    expect(validateArtifact({ ...findArtifact(golden, 'ScanRun'), schema_name: 'InventedReceipt' })).toBe(
      'contract_schema_unregistered',
    );
  });
});

describe('fixtures select inputs, never outcomes', () => {
  it('produces identical values when only the bundle identifier changes', () => {
    const renamed = clone(golden);
    renamed.bundle_id = 'a-completely-different-fixture-name';
    renamed.provenance = { ...renamed.provenance, note: 'renamed fixture' };
    const at = { now: new Date('2026-08-22T09:00:00Z') };
    expect(buildViewModel(renamed, at).fields).toEqual(buildViewModel(golden, at).fields);
  });

  it('changes the rendered value when the authoritative artifact changes', () => {
    const copy = clone(golden);
    findArtifact(copy, 'PolicyDecision').outcome = 'NO_ACTION';
    expect(buildViewModel(copy).fields['UI-POLICY-OUTCOME'].value).toBe('NO_ACTION');
    expect(buildViewModel(golden).fields['UI-POLICY-OUTCOME'].value).toBe('REVIEW_REQUIRED');
  });
});

describe('freshness', () => {
  it('marks the surface stale when the newest artifact is outside the window', () => {
    const fresh = buildViewModel(golden, { now: new Date('2026-08-22T09:05:00Z') });
    const stale = buildViewModel(golden, { now: new Date('2026-08-23T09:00:00Z') });
    expect(fresh.fields['UI-GLOBAL-UPDATED'].status).toBe('KNOWN');
    expect(stale.fields['UI-GLOBAL-UPDATED'].status).toBe('STALE');
    expect(stale.fields['UI-GLOBAL-UPDATED'].value).toBe(fresh.fields['UI-GLOBAL-UPDATED'].value);
  });
});
