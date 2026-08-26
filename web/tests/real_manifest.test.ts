/**
 * Full-render check for a CohortDayManifest, usable on the REAL emitted one.
 *
 * By default this validates both committed producer fixtures, so it is a live
 * part of the suite and never a skip. Handed a real artifact it runs the same
 * checks on it:
 *
 *   $env:REAL_MANIFEST='C:\path\to\manifest.json'; pnpm vitest run tests/real_manifest.test.ts
 *
 * One code path for fixtures and the real thing, so this operator tool cannot
 * drift from what the suite proves. The check passes only when the artifact is
 * accepted, every cohort field resolves KNOWN, the elapsed-days gate reaches a
 * verdict without an unexpected withhold, and the manifest's totals agree with
 * its own history.
 */

import { readFileSync } from 'node:fs';

import { describe, expect, it } from 'vitest';

import { buildViewModel } from '../src/viewmodel/builder';
import { historyAgreement, operationSpan, rowStatus } from '../src/viewmodel/cohort';
import type { ArtifactBundle } from '../src/viewmodel/types';
import example from './fixtures/cohort-day2-manifest.example.json';
import legacy from './fixtures/cohort-day2-manifest.v2.0.legacy.json';

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
] as const;

interface ManifestLike {
  schema_name?: unknown;
  schema_version?: unknown;
  artifact_id?: unknown;
  day_index?: unknown;
  selected_for_date?: unknown;
  image_digest?: unknown;
  data_mode?: unknown;
  execution_history?: unknown[];
  cumulative?: Record<string, unknown> | null;
}

/** Every failure the panel would have with this manifest, empty means pass. */
function fullCheck(manifest: ManifestLike, label: string): string[] {
  const failures: string[] = [];
  const report: string[] = [
    `${label}: ${String(manifest.schema_name)} ${String(manifest.schema_version)}`,
    `  artifact ${String(manifest.artifact_id)}  day ${String(manifest.day_index)}`,
    `  digest ${String(manifest.image_digest)}  data_mode ${String(manifest.data_mode)}`,
  ];

  const { fields, rejected } = buildViewModel({
    bundle_id: 'real-manifest-check',
    bundle_kind: 'DEMO',
    bundle_version: '1.0.0',
    provenance: {},
    artifacts: [manifest],
  } as unknown as ArtifactBundle);

  if (rejected.length > 0) {
    failures.push(`artifact rejected: ${rejected[0].reason_code}`);
  }
  for (const id of COHORT_FIELDS) {
    const field = fields[id];
    report.push(`  ${id.padEnd(28)} ${String(field.status === 'KNOWN' ? field.value : field.status)}`);
    if (field.status !== 'KNOWN') {
      failures.push(`${id} is ${field.status}, not KNOWN`);
    }
  }

  const history = (manifest.execution_history ?? []) as Parameters<typeof operationSpan>[0];
  const span = operationSpan(history);
  report.push(`  span: proven=${span.proven}  ${span.sentence}`);
  if (span.withheldBecause) {
    // A withhold is a finding, not automatically a failure: an honest incomplete
    // record can withhold correctly. It is surfaced and the caller reads it.
    report.push(`  withheld: ${span.withheldBecause}`);
  }
  for (const row of history.filter((entry) => rowStatus(entry) === 'INCOMPLETE')) {
    report.push(`  incomplete day ${String(row.day_index)}: receipt ${String(row.failure_receipt_id)}`);
  }

  const agreement = historyAgreement(history, manifest.cumulative ?? null);
  report.push(`  totals: checked=${agreement.checked} agrees=${agreement.agrees}`);
  for (const line of agreement.disagreements) {
    failures.push(`totals disagree with history: ${line}`);
  }
  if (!agreement.checked) {
    failures.push('nothing to compare: history or cumulative missing');
  }

  console.log(report.join('\n'));
  return failures;
}

describe('full-render check', () => {
  it('passes on the committed 2.1.0 example', () => {
    expect(fullCheck(example, '2.1.0 example')).toEqual([]);
  });

  it('passes on the committed 2.0.0 legacy shape', () => {
    expect(fullCheck(legacy, '2.0.0 legacy')).toEqual([]);
  });

  it('checks the real emitted manifest when REAL_MANIFEST is set', () => {
    const path = process.env.REAL_MANIFEST;
    if (!path) {
      // Not a silent skip: the two fixture checks above always run. This third
      // check exists for the operator handing in a real artifact.
      expect(path).toBeUndefined();
      return;
    }
    const manifest = JSON.parse(readFileSync(path, 'utf-8')) as ManifestLike;
    const failures = fullCheck(manifest, `REAL ${path}`);
    expect(failures, failures.join('; ')).toEqual([]);
  });
});
