/**
 * The two demo surfaces the storyboard names by build item.
 *
 * The DENIED frame is governed by the comprehension gate: a first-time viewer
 * must understand what was refused and why. The headline is composed from the
 * receipt's own fields, so these tests drive it from a real bundle rather than
 * asserting a string.
 *
 * The resolution-mode badge reads RegistryResolutionReceipt rather than
 * RoutingPlan, which nothing produces at all. That value is not evidence of a
 * resolution: no production path emits this receipt today, and the only emitter
 * is a fixture carrying a string constant on a SYNTHETIC artifact with no
 * bindings. The badge therefore shows the source's data mode beside the value,
 * so a constant can never read as a live fact.
 */

import { describe, expect, it } from 'vitest';

import faultBundle from '../src/bundles/fault.json';
import goldenBundle from '../src/bundles/golden.json';
import { buildViewModel } from '../src/viewmodel/builder';
import { denialHeadline, resolutionModeCopy, resolutionSourceCopy } from '../src/viewmodel/semantics';
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
  it('reads RegistryResolutionReceipt rather than the never-produced RoutingPlan', () => {
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

  it('shows the data mode of the artifact the value came from', () => {
    const { fields } = buildViewModel(golden);
    const source = fields['UI-CLOUD-RESOLUTION-SOURCE'];
    expect(source.status).toBe('KNOWN');
    expect(String(source.value)).toBe('SYNTHETIC');
  });

  it('says a fixture-declared value is declared, never observed', () => {
    const copy = resolutionSourceCopy('SYNTHETIC').plain;
    expect(copy).toContain('fixture');
    expect(copy).not.toContain('Observed');
  });

  it('reserves the observed wording for a non-synthetic source', () => {
    expect(resolutionSourceCopy('LIVE_PUBLIC').plain).toContain('Observed');
    expect(resolutionSourceCopy('MOCK').plain).toContain('fixture');
  });

  it('does not claim registry discovery when the run fell back', () => {
    const copy = resolutionModeCopy('PINNED_FALLBACK').plain;
    expect(copy).toContain('pinned manifest');
    expect(copy).not.toContain('live agent registry');
  });
});
