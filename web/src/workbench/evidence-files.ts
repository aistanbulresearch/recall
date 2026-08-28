/**
 * Evidence-file registry: derived values read from committed evidence JSON
 * files that are not contract artifacts (no envelope), such as the privacy
 * run's RUN_MANIFEST. The same discipline as the view-model registry applies:
 * a component may only show a figure that is listed here with its json path
 * and source file, so the substrate strip can print the full lineage.
 *
 * DRAFT NOTE (2026-08-29 night build): gemma-run-manifest.json is a verbatim
 * copy of artifacts/evidence/full-cohort-receipts/RUN_MANIFEST.json produced
 * by the 462-case run on the int-v4 tree (code_source_commit inside the file);
 * the morning final bundle regeneration may formalize it as a contract
 * artifact, at which point this file-level registry entry retires.
 */

import gemmaRunManifest from '../data/gemma-run-manifest.json';
import historicalCase from '../data/historical-case.json';
import p1Report from '../data/p1-privacy-report.json';

import type { StripEntry } from './strip';

const GEMMA_FILE = 'data/gemma-run-manifest.json';
const CASE_FILE = 'data/historical-case.json';

type Json = Record<string, unknown>;

function read(source: Json, path: string): unknown {
  let cursor: unknown = source;
  for (const part of path.replace(/^\$\./, '').split('.')) {
    if (cursor === null || typeof cursor !== 'object') {
      return null;
    }
    cursor = (cursor as Json)[part];
  }
  return cursor ?? null;
}

function entry(
  file: string,
  source: Json,
  key: string,
  label: string,
  path: string,
): StripEntry {
  const value = read(source, path);
  return {
    key,
    label,
    value: value === null ? null : typeof value === 'object' ? JSON.stringify(value) : (value as string | number),
    status: value === null ? 'UNKNOWN' : 'KNOWN',
    lineage: `${path} ← ${file}`,
  };
}

const gemma = gemmaRunManifest as unknown as Json;
const hero = historicalCase as unknown as Json;

/** The privacy run figures the clinician-facing privacy view may show. */
export const GEMMA_RUN_FIELDS: Record<string, StripEntry> = Object.fromEntries(
  (
    [
      ['EV-GEMMA-RECEIPTS', 'Receipts produced', '$.receipt_count'],
      ['EV-GEMMA-ELAPSED', 'Run duration (min)', '$.elapsed_minutes'],
      ['EV-GEMMA-POSTURE', 'Execution posture', '$.posture'],
      ['EV-GEMMA-LOCUS', 'Endpoint class', '$.locus.endpoint_class'],
      ['EV-GEMMA-TRANSPORT', 'Transport class', '$.locus.transport_class'],
      ['EV-GEMMA-EXEC-LOCUS', 'Execution locus', '$.locus.execution_locus'],
      ['EV-GEMMA-MODEL', 'Model', '$.locus.model_id'],
      ['EV-GEMMA-MODEL-REV', 'Model revision', '$.locus.model_revision'],
      ['EV-GEMMA-WIRE-SHA', 'Receipt file sha256', '$.receipts_sha256'],
      ['EV-GEMMA-NOTES-SHA', 'Input notes sha256', '$.notes_sha256'],
      ['EV-GEMMA-FINGERPRINT', 'Verifier-lock fingerprint', '$.verifier_lock_fingerprint_sha256'],
      ['EV-GEMMA-COMMIT', 'Code source commit', '$.code_source_commit'],
      ['EV-GEMMA-DIRTY', 'Code source dirty', '$.code_source_dirty'],
      ['EV-GEMMA-STARTED', 'Started (UTC)', '$.started_at'],
      ['EV-GEMMA-FINISHED', 'Finished (UTC)', '$.finished_at'],
      ['EV-GEMMA-HELD-OUT', 'Held-out cases', '$.held_out_inherit_binding'],
    ] as const
  ).map(([key, label, path]) => [key, entry(GEMMA_FILE, gemma, key, label, path)]),
);

/** The historical hero case: dates and rulings, straight from the case file. */
export const HERO_CASE_FIELDS: Record<string, StripEntry> = Object.fromEntries(
  (
    [
      ['EV-HERO-GENE', 'Gene', '$.gene'],
      ['EV-HERO-VARIANT', 'Variant', '$.variant'],
      ['EV-HERO-VCV', 'ClinVar VCV', '$.clinvar_vcv'],
      ['EV-HERO-GEO', 'Data deposit (GEO)', '$.geo_accession'],
      ['EV-HERO-PMID', 'Qualifying publication', '$.qualifying_pmid'],
      ['EV-HERO-DATE-DATA', 'Data deposit public (GEO)', '$.dates.geo_public'],
      ['EV-HERO-DATE-PAPER', 'Qualifying publication', '$.dates.qualifying_publication'],
      ['EV-HERO-DATE-CLINVAR', 'ClinVar v5 public', '$.dates.clinvar_v5_public'],
      ['EV-HERO-RULING', 'Claim-gate ruling', '$.claim_gate_ruling'],
      ['EV-HERO-CAVEAT', 'Start-date caveat', '$.start_date_caveat'],
    ] as const
  ).map(([key, label, path]) => [key, entry(CASE_FILE, hero, key, label, path)]),
);

const P1_FILE = 'data/p1-privacy-report.json';
const p1 = p1Report as unknown as Json;

/**
 * Frozen P1 privacy study. Arm labels travel with the figures: arm B is the
 * declared-secondary exploratory arm and is always shown with that label
 * (read from the report itself, never asserted by the component).
 */
export const P1_FIELDS: Record<string, StripEntry> = Object.fromEntries(
  (
    [
      ['EV-P1-BASELINE-ACCEPTED', 'Baseline accepted', '$.baseline.combined.document_level.accepted'],
      ['EV-P1-BASELINE-RECORDS', 'Baseline records', '$.baseline.combined.document_level.records'],
      ['EV-P1-ARM-B-ACCEPTED', 'With Gemma (arm B) accepted', '$.comparison_arm_b.combined.document_level.accepted'],
      ['EV-P1-ARM-B-RECORDS', 'With Gemma (arm B) records', '$.comparison_arm_b.combined.document_level.records'],
      ['EV-P1-ARM-B-STATUS', 'Arm B declared status', '$.arms.secondary.status'],
      ['EV-P1-ESCAPES-BASE', 'Escaped identifiers (baseline)', '$.baseline.combined.document_level.escaped_direct_identifier_surfaces'],
      ['EV-P1-ESCAPES-ARM-B', 'Escaped identifiers (arm B)', '$.comparison_arm_b.combined.document_level.escaped_direct_identifier_surfaces'],
      ['EV-P1-STRUCTURED-ACCEPTED', 'Structured-only egress accepted', '$.structured_only_egress.combined.document_level.accepted'],
      ['EV-P1-STRUCTURED-RECORDS', 'Structured-only egress records', '$.structured_only_egress.combined.document_level.records'],
      ['EV-P1-RUN-ID', 'Frozen run id', '$.frozen_test_run_id'],
      ['EV-P1-PROTOCOL', 'Protocol version', '$.protocol_version'],
      ['EV-P1-CONTENT-HASH', 'Report content hash', '$.content_hash'],
    ] as const
  ).map(([key, label, path]) => [key, entry(P1_FILE, p1, key, label, path)]),
);

export { gemmaRunManifest, historicalCase, p1Report };
