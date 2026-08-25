/**
 * The two demo surfaces the storyboard names by build item.
 *
 * The DENIED frame is governed by the comprehension gate: a first-time viewer
 * must understand what was refused and why. The headline is composed from the
 * receipt's own fields, so these tests drive it from a real bundle rather than
 * asserting a string. The resolution-mode badge reads
 * RegistryResolutionReceipt, which a live run produces, and never RoutingPlan,
 * which nothing produces.
 */

import { describe, expect, it } from 'vitest';

import faultBundle from '../src/bundles/fault.json';
import goldenBundle from '../src/bundles/golden.json';
import { buildViewModel } from '../src/viewmodel/builder';
import { denialHeadline, resolutionModeCopy } from '../src/viewmodel/semantics';
import type { ArtifactBundle } from '../src/viewmodel/types';

const golden = goldenBundle as unknown as ArtifactBundle;
const fault = faultBundle as unknown as ArtifactBundle;

function receiptProperties(bundle: ArtifactBundle): Record<string, unknown> {
  const { fields } = buildViewModel(bundle);
  const denial = fields['UI-TOOL-DENIAL'];
  const properties: Record<string, unknown> = {};
  for (const entry of denial.items) {
    if (typeof entry === 'object' && entry !== null && 'property' in entry) {
      const typed = entry as { property: string; value: unknown };
      properties[typed.property] = typed.value;
    }
  }
  return properties;
}

describe('DENIED frame, comprehension gate', () => {
  it('names what was refused, not only that a refusal happened', () => {
    const headline = denialHeadline(receiptProperties(fault));
    expect(headline).not.toBeNull();
    const text = String(headline);
    expect(text).toContain('evidence assessor');
    expect(text).toContain('review-task-writer');
    expect(text).toContain('create review task');
  });

  it('says why, in ordinary words rather than a bare reason code', () => {
    const text = String(denialHeadline(receiptProperties(fault)));
    expect(text).toContain('not in this role tool scope');
    expect(text).not.toContain('tool_not_allowlisted');
  });

  it('is built from receipt fields, so every part traces to the artifact', () => {
    const properties = receiptProperties(fault);
    const text = String(denialHeadline(properties));
    for (const key of ['agent_role', 'tool_id', 'requested_action']) {
      const raw = String(properties[key]).toLowerCase().replace(/_/g, ' ');
      expect(text.toLowerCase()).toContain(raw);
    }
  });

  it('returns nothing rather than inventing a sentence when fields are missing', () => {
    expect(denialHeadline({})).toBeNull();
    expect(denialHeadline({ agent_role: 'X' })).toBeNull();
  });

  it('omits the reason clause rather than guessing when no code is present', () => {
    const text = String(denialHeadline({ agent_role: 'EVIDENCE_ASSESSOR', tool_id: 't', reason_codes: [] }));
    expect(text).toBe('The evidence assessor was refused t.');
  });
});

describe('resolution mode badge', () => {
  it('reads RegistryResolutionReceipt, which a live run produces', () => {
    const { fields } = buildViewModel(golden);
    const mode = fields['UI-CLOUD-RESOLUTION-MODE'];
    expect(mode.status).toBe('KNOWN');
    expect(String(mode.value)).toBe('PINNED_FALLBACK');
    expect(mode.source_refs.length).toBeGreaterThan(0);
  });

  it('goes UNKNOWN when its source artifact is absent, never a default', () => {
    const stripped = {
      ...golden,
      artifacts: golden.artifacts.filter((a) => a.schema_name !== 'RegistryResolutionReceipt'),
    } as ArtifactBundle;
    const { fields } = buildViewModel(stripped);
    expect(fields['UI-CLOUD-RESOLUTION-MODE'].status).toBe('UNKNOWN');
    expect(fields['UI-CLOUD-RESOLUTION-MODE'].value).toBeNull();
  });

  it('carries plain copy for every registered mode', () => {
    for (const mode of ['REGISTRY', 'MANUAL_SERVICE', 'PINNED_FALLBACK']) {
      expect(resolutionModeCopy(mode).plain.length).toBeGreaterThan(10);
    }
  });

  it('does not claim registry discovery when the run fell back', () => {
    const copy = resolutionModeCopy('PINNED_FALLBACK').plain;
    expect(copy).toContain('pinned manifest');
    expect(copy).not.toContain('live agent registry');
  });
});
