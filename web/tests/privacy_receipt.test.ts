/**
 * The PrivacyReceipt inside each bundle is produced by the laboratory Privacy
 * Gate in this repository, so the surface reads a real artifact, not a mock.
 */

import { describe, expect, it } from 'vitest';

import faultBundle from '../src/bundles/fault.json';
import goldenBundle from '../src/bundles/golden.json';
import { buildViewModel } from '../src/viewmodel/builder';
import type { ArtifactBundle, ArtifactEnvelope } from '../src/viewmodel/types';

function receiptOf(bundle: ArtifactBundle): ArtifactEnvelope {
  const receipt = bundle.artifacts.find((artifact) => artifact.schema_name === 'PrivacyReceipt');
  if (!receipt) {
    throw new Error('bundle is missing the privacy receipt');
  }
  return receipt;
}

const golden = goldenBundle as unknown as ArtifactBundle;
const fault = faultBundle as unknown as ArtifactBundle;

describe('privacy receipt in the bundle', () => {
  it('carries the contract payload fields', () => {
    const receipt = receiptOf(golden);
    for (const field of [
      'decision',
      'detector_versions',
      'identifier_classes_checked',
      'detectors',
      'outbound',
      'payload_hash',
      'signature_ref',
    ]) {
      expect(receipt, field).toHaveProperty(field);
    }
  });

  it('reports zero raw text fields for an accepted decision', () => {
    const receipt = receiptOf(golden);
    expect(receipt.decision).toBe('ACCEPTED');
    expect((receipt.outbound as { raw_text_field_count: number }).raw_text_field_count).toBe(0);
  });

  it('never carries a raw span surface', () => {
    const spans = (receiptOf(golden).detectors as { deterministic: { approved_spans: Array<Record<string, unknown>> } })
      .deterministic.approved_spans;
    expect(spans.length).toBeGreaterThan(0);
    for (const span of spans) {
      expect(Object.keys(span).sort()).toEqual(['end', 'identifier_class', 'span_hash', 'start']);
    }
  });

  it('surfaces the privacy fields through the view model', () => {
    const { fields } = buildViewModel(golden);
    expect(fields['UI-PRIVACY-STATUS'].value).toBe('ACCEPTED');
    expect(fields['UI-PRIVACY-RAW-TEXT-EGRESS'].value).toBe(0);
    expect(Number(fields['UI-PRIVACY-DETERMINISTIC-SPANS'].value)).toBeGreaterThan(0);
    expect(Number(fields['UI-PRIVACY-GEMMA-SPANS'].value)).toBeGreaterThan(0);
  });

  it('reports the same privacy evidence in the fault fixture', () => {
    const { fields } = buildViewModel(fault);
    expect(fields['UI-PRIVACY-RAW-TEXT-EGRESS'].value).toBe(0);
    expect(fields['UI-PRIVACY-STATUS'].status).toBe('KNOWN');
  });
});
