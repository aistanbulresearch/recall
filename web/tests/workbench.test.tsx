/**
 * Clinical Evidence Workbench: honesty invariants.
 *
 * The clinician layer is presentation only — these tests pin the rules that
 * make it honest: stamps derive from gate/run fields, day counts are computed
 * from dates at render time, PENDING placeholders never carry figures, and
 * evidence-file chips resolve real committed values.
 */

import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';

import faultBundle from '../src/bundles/fault.json';
import goldenBundle from '../src/bundles/golden.json';
import haltedBundle from '../src/bundles/halted.json';
import { buildViewModel } from '../src/viewmodel/builder';
import type { ArtifactBundle } from '../src/viewmodel/types';
import { GEMMA_RUN_FIELDS, P1_FIELDS, P1_SUPERSEDED } from '../src/workbench/evidence-files';
import { StripProvider } from '../src/workbench/strip';
import { HeroCase } from '../src/workbench/views/HeroCase';
import { PrivacyDesk } from '../src/workbench/views/PrivacyDesk';
import { Worklist, recordStamp } from '../src/workbench/views/Worklist';

const golden = buildViewModel(goldenBundle as unknown as ArtifactBundle);
const fault = buildViewModel(faultBundle as unknown as ArtifactBundle);
const halted = buildViewModel(haltedBundle as unknown as ArtifactBundle);

function render(node: React.ReactElement): string {
  return renderToStaticMarkup(<StripProvider>{node}</StripProvider>);
}

describe('record stamps derive from fields', () => {
  it('maps a decided gate outcome to its fixed plain-language label', () => {
    expect(recordStamp(golden.fields)).toEqual({
      label: 'Human review requested',
      tone: 'review',
    });
    expect(recordStamp(fault.fields)).toEqual({
      label: 'Fleet abstained — evidence did not verify',
      tone: 'abstain',
    });
  });

  it('speaks through the run state when the gate never decided', () => {
    // The halted fixture's gate outcome is honestly INCOMPLETE; the stamp must
    // say the run halted, not invent an outcome.
    expect(halted.fields['UI-POLICY-OUTCOME'].status).toBe('INCOMPLETE');
    expect(recordStamp(halted.fields)).toEqual({
      label: 'Run halted — the gate never decided',
      tone: 'halted',
    });
  });
});

describe('hero case chronology', () => {
  it('computes both rulings-approved intervals from the dates at render time', () => {
    const markup = render(<HeroCase />);
    // Registry-chronology headline and the preregistered lead-time beside it,
    // per the 2026-08-25 claim-gate ruling recorded in the case file.
    expect(markup).toContain('575 days');
    expect(markup).toContain('472 days');
    expect(markup).toContain('Preregistered lead-time metric');
    expect(markup).toContain('Registry chronology');
  });

  it('keeps the honesty sentences on the page', () => {
    const markup = render(<HeroCase />);
    expect(markup).toContain('conflicting, not uniformly pathogenic');
    expect(markup).toContain('does not establish that the paper caused');
    expect(markup).toContain('not a product metric');
  });
});

describe('worklist honesty', () => {
  function worklistMarkup(): string {
    return render(
      <Worklist
        scenarios={[
          {
            id: 'golden',
            label: 'g',
            clinicalLabel: 'Re-evaluation completed — audited replay',
            bundle: goldenBundle as unknown as ArtifactBundle,
          },
        ]}
        models={{ golden }}
      />,
    );
  }

  it('pending rows carry no figures — only the PENDING stamp and prose', () => {
    const markup = worklistMarkup();
    const pendingBlock = markup.slice(markup.indexOf('Pending cohort results'));
    const rows = pendingBlock.match(/work-row pending[\s\S]*?<\/div>/g) ?? [];
    expect(rows.length).toBeGreaterThan(0);
    for (const row of rows) {
      // r1/r2/r3 ramp names are the only digits allowed in a pending row.
      const stripped = row.replace(/Ramp r[123]/g, '');
      expect(stripped).not.toMatch(/\d/);
    }
  });

  it('keeps the run-vs-case footnote on the page', () => {
    expect(worklistMarkup()).toContain('Run counts and case counts are different things');
  });
});

describe('privacy desk evidence chips', () => {
  it('resolves the frozen P1 figures from the committed report', () => {
    expect(P1_FIELDS['EV-P1-BASELINE-ACCEPTED'].value).toBe(0);
    expect(P1_FIELDS['EV-P1-BASELINE-RECORDS'].value).toBe(180);
    expect(P1_FIELDS['EV-P1-ARM-B-ACCEPTED'].value).toBe(136);
    expect(P1_FIELDS['EV-P1-ESCAPES-ARM-B'].value).toBe(0);
  });

  it('takes its arm declarations from the corrected view, not the raw report', () => {
    // Amendment 001 made surface_exact_search the primary arm. The raw report
    // still says otherwise, and a surface that repeats it publishes a
    // superseded declaration.
    expect(P1_FIELDS['EV-P1-PRIMARY-ARM'].value).toBe('surface_exact_search');
    expect(P1_FIELDS['EV-P1-PRIMARY-STATUS'].value).toBe('primary under amendment 001');
    expect(P1_FIELDS['EV-P1-SECONDARY-ARM'].value).toBe('model_offsets');
    for (const field of Object.values(P1_FIELDS)) {
      expect(field.lineage).toContain('p1-corrected-view.json');
    }
    expect(P1_SUPERSEDED.value).toBe('declared secondary, exploratory');
    expect(P1_SUPERSEDED.lineage).toContain('p1-privacy-report.json');
  });

  it('resolves the full-cohort run figures from the committed manifest', () => {
    expect(GEMMA_RUN_FIELDS['EV-GEMMA-RECEIPTS'].value).toBe(462);
    expect(GEMMA_RUN_FIELDS['EV-GEMMA-DIRTY'].value).toBe(false);
    expect(GEMMA_RUN_FIELDS['EV-GEMMA-LOCUS'].value).toBe('OLLAMA_VERTEX_ENDPOINT');
    expect(String(GEMMA_RUN_FIELDS['EV-GEMMA-COMMIT'].value)).toMatch(/^697aa6eb/);
  });

  it('renders the corrected arm declarations, and the superseded one as a correction', () => {
    const markup = render(<PrivacyDesk />);
    expect(markup).toContain('primary under amendment 001');
    expect(markup).toContain('surface_exact_search');
    // The old label may appear only inside the sentence that calls it superseded.
    const supersededIndex = markup.indexOf('declared secondary, exploratory');
    expect(supersededIndex).toBeGreaterThan(-1);
    expect(markup.slice(0, supersededIndex)).toContain('The raw manifest still declares');
    expect(markup).toContain('462');
  });

  it('every evidence chip carries its lineage', () => {
    for (const entry of [...Object.values(P1_FIELDS), ...Object.values(GEMMA_RUN_FIELDS)]) {
      expect(entry.lineage).toMatch(/^\$\..+ ← data\//);
    }
  });
});
