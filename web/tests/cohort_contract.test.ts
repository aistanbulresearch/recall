/**
 * The panel against the REAL contract example, not against a fixture I wrote.
 *
 * Every other cohort test uses manifests this lane authored to its own idea of
 * the contract, which proves the panel is self-consistent and nothing more. This
 * file loads the example manifest committed by the producing lane and asserts
 * that every field the panel displays actually resolves from it.
 *
 * The fixture is a byte-identical copy of
 * `artifacts/evidence/cohort-manifest-example/day2-manifest.synthetic.json`
 * on feature/rcl-3xx-core, git blob a04588fd237cc36286799a5641ae814b4195105d.
 * If the producer changes the shape, this test is where it should break, and it
 * should break loudly rather than degrade into a screen of UNKNOWN.
 */

import { describe, expect, it } from 'vitest';

import { buildViewModel } from '../src/viewmodel/builder';
import { historyAgreement, caseModeCopy, operationSpan } from '../src/viewmodel/cohort';
import type { ArtifactBundle } from '../src/viewmodel/types';
import manifest from './fixtures/cohort-day2-manifest.example.json';

function bundle(): ArtifactBundle {
  return {
    bundle_id: 'contract-example',
    bundle_kind: 'DEMO',
    bundle_version: '1.0.0',
    provenance: {},
    artifacts: [manifest],
  } as unknown as ArtifactBundle;
}

describe('the real 2.0.0 manifest is accepted', () => {
  it('is the version the panel binds to', () => {
    expect(manifest.schema_name).toBe('CohortDayManifest');
    expect(manifest.schema_version).toBe('2.0.0');
  });

  it('passes envelope validation rather than being rejected', () => {
    const { rejected, acceptedArtifactCount } = buildViewModel(bundle());
    expect(rejected).toEqual([]);
    expect(acceptedArtifactCount).toBe(1);
  });
});

describe('every cohort field resolves from the real manifest', () => {
  const COHORT_FIELDS = [
    'UI-COHORT-DAY-INDEX',
    'UI-COHORT-CASES-DELTA',
    'UI-COHORT-RUNS-DELTA',
    'UI-COHORT-RUNS-TOTAL',
    'UI-COHORT-CYCLES-TOTAL',
    'UI-COHORT-DISTINCT-DATES',
    'UI-COHORT-IMAGE-DIGEST',
    'UI-COHORT-SOURCE-COMMIT',
    'UI-COHORT-DATA-MODE',
    'UI-COHORT-CASES',
    'UI-COHORT-VCV-ANCHORS',
    'UI-COHORT-EXECUTIONS',
  ];

  it('resolves all of them, so none renders UNKNOWN on the day it matters', () => {
    const { fields } = buildViewModel(bundle());
    const unresolved = COHORT_FIELDS.filter((id) => fields[id].status !== 'KNOWN');
    expect(unresolved).toEqual([]);
  });

  it('carries lineage for every one', () => {
    const { fields } = buildViewModel(bundle());
    for (const id of COHORT_FIELDS) {
      expect(fields[id].source_refs.length, id).toBeGreaterThan(0);
    }
  });

  it('counts the day by identity, not by a tally the manifest does not carry', () => {
    const { fields } = buildViewModel(bundle());
    expect(fields['UI-COHORT-CASES-DELTA'].value).toBe(manifest.delta.selected_case_ids.length);
    expect(fields['UI-COHORT-RUNS-DELTA'].value).toBe(manifest.delta.newly_created_run_ids.length);
  });

  it('does not count reused runs as work created today', () => {
    // The real example has an EMPTY reused list, so newly_created and
    // authoritative are the same number there and no assertion against it can
    // tell the two apart. A day with reuse is constructed here so the check can
    // actually discriminate, which the real manifest alone cannot.
    const withReuse = {
      ...manifest,
      delta: {
        ...manifest.delta,
        reused_run_ids: ['00000000-0000-5000-8000-000000000001'],
        authoritative_run_ids: [
          ...manifest.delta.newly_created_run_ids,
          '00000000-0000-5000-8000-000000000001',
        ],
      },
    };
    const { fields } = buildViewModel({
      bundle_id: 'reuse',
      bundle_kind: 'DEMO',
      bundle_version: '1.0.0',
      provenance: {},
      artifacts: [withReuse],
    } as unknown as ArtifactBundle);

    expect(fields['UI-COHORT-RUNS-DELTA'].value).toBe(manifest.delta.newly_created_run_ids.length);
    expect(fields['UI-COHORT-RUNS-DELTA'].value).not.toBe(withReuse.delta.authoritative_run_ids.length);
  });
});

describe('the manifest agrees with its own history', () => {
  it('totals reconcile against the rows they were derived from', () => {
    const check = historyAgreement(manifest.execution_history, manifest.cumulative);
    expect(check.checked).toBe(true);
    expect(check.disagreements).toEqual([]);
    expect(check.agrees).toBe(true);
  });

  it('reports a disagreement rather than picking a side', () => {
    const check = historyAgreement(manifest.execution_history, {
      ...manifest.cumulative,
      daily_cycles: 99,
    });
    expect(check.agrees).toBe(false);
    expect(check.disagreements.join(' ')).toContain('daily cycles');
    expect(check.disagreements.join(' ')).toContain('99');
  });

  it('does not claim agreement when there is nothing to compare', () => {
    expect(historyAgreement([], manifest.cumulative).checked).toBe(false);
    expect(historyAgreement(manifest.execution_history, null).checked).toBe(false);
  });
});

describe('the real history satisfies the elapsed-days gate', () => {
  it('proves the span from the manifest’s own rows', () => {
    const span = operationSpan(manifest.execution_history);
    expect(span.proven).toBe(true);
    expect(span.distinctDays).toBe(manifest.cumulative.distinct_execution_dates);
  });
});

describe('case modes are the ones the contract permits', () => {
  it('describes every mode present without falling through to the default', () => {
    for (const entry of manifest.cases) {
      expect(caseModeCopy(entry.data_mode).plain, entry.data_mode).not.toContain('not declared');
    }
  });

  it('treats a null vcv as unanchored, which the contract guarantees', () => {
    // 2.0.0 enforces vcv === null exactly when the mode is SYNTHETIC_ONLY.
    for (const entry of manifest.cases) {
      expect(caseModeCopy(entry.data_mode).anchored, entry.case_id).toBe(entry.vcv !== null);
    }
  });
});
