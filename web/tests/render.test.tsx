/** Component rendering: distinct states, lineage, and no leaked identifiers. */

import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';

import faultBundle from '../src/bundles/fault.json';
import goldenBundle from '../src/bundles/golden.json';
import haltedBundle from '../src/bundles/halted.json';
import { FieldValue, MissingLineageError } from '../src/components/FieldValue';
import { MissionControl } from '../src/components/MissionControl';
import { buildViewModel } from '../src/viewmodel/builder';
import type { ArtifactBundle, ViewField } from '../src/viewmodel/types';

const golden = goldenBundle as unknown as ArtifactBundle;
const fault = faultBundle as unknown as ArtifactBundle;
const halted = haltedBundle as unknown as ArtifactBundle;

function render(bundle: ArtifactBundle): string {
  return renderToStaticMarkup(<MissionControl model={buildViewModel(bundle).fields} />);
}

describe('mission control rendering', () => {
  it('renders the audited fixture with its derived outcome', () => {
    const markup = render(golden);
    expect(markup).toContain('data-outcome="REVIEW_REQUIRED"');
    expect(markup).toContain('data-field-id="UI-TASK-COUNT-RUN"');
    expect(markup).toContain('NON-CLINICAL RESEARCH PROTOTYPE');
  });

  it('renders the fault fixture as an abstention with a visible denial', () => {
    const markup = render(fault);
    expect(markup).toContain('data-outcome="ABSTAIN"');
    expect(markup).toContain('data-field-id="UI-TOOL-DENIAL"');
    expect(markup).toContain('tool_not_allowlisted');
  });

  it('shows no denial panel when no denial receipt exists', () => {
    expect(render(golden)).not.toContain('data-field-id="UI-TOOL-DENIAL"');
  });

  it('renders technical HALTED with a different treatment from ABSTAIN', () => {
    const haltedMarkup = render(halted);
    const faultMarkup = render(fault);
    expect(haltedMarkup).toContain('data-run-state="HALTED"');
    expect(faultMarkup).toContain('data-run-state="ABSTAIN"');
    expect(haltedMarkup).not.toContain('data-outcome="ABSTAIN"');
    expect(haltedMarkup).toContain('This is not a policy outcome');
  });

  it('renders the privacy decision derived from the receipt', () => {
    expect(render(golden)).toContain('data-privacy-decision="ACCEPTED"');
  });

  it('marks every missing field with its status rather than a zero', () => {
    const markup = render(halted);
    expect(markup).toContain('data-status="INCOMPLETE"');
    expect(markup).toMatch(/data-field-id="UI-POLICY-OUTCOME" data-status="INCOMPLETE"/);
  });

  it('exposes source lineage for every rendered result field', () => {
    const markup = render(golden);
    expect(markup).toContain('view-model-builder@1.0.0');
    expect((markup.match(/<summary>Source<\/summary>/g) ?? []).length).toBeGreaterThan(10);
  });

  it('never renders raw institutional text or a redaction placeholder', () => {
    for (const bundle of [golden, fault, halted]) {
      const markup = render(bundle);
      expect(markup).not.toContain('[PERSON_NAME]');
      expect(markup).not.toContain('TC Kimlik No');
      expect(markup).not.toContain('Hasta:');
    }
  });
});

describe('lineage is mandatory', () => {
  it('refuses to render a known value without a source reference', () => {
    const field: ViewField = {
      field_id: 'UI-POLICY-OUTCOME',
      label: 'Outcome',
      value: 'REVIEW_REQUIRED',
      items: [],
      status: 'KNOWN',
      source_refs: [],
      derived_by: 'test',
      derived_at: '2026-08-22T09:00:00Z',
      hidden: false,
    };
    expect(() => renderToStaticMarkup(<FieldValue field={field} />)).toThrow(MissingLineageError);
  });
});
