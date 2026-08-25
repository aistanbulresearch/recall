/**
 * The evidence card is never cut, so its facts are held to the governing
 * document rather than trusted.
 *
 * Two properties matter more than the rest. Intervals are computed from the
 * dates, so no displayed number can disagree with the dates beside it. And each
 * interval carries its own status, so the one the governing document calls the
 * preregistered metric is the only one labelled that way.
 */

import { describe, expect, it } from 'vitest';

// Imported as raw text so the test reads the governing document itself rather
// than a copy of it, without pulling node typings into the web build.
import GOVERNING from '../../docs/evaluation/HISTORICAL_REPLAY_CASE.md?raw';
import caseData from '../src/data/historical-case.json';
import { daysBetween, intervalDays } from '../src/components/EvidenceCard';

describe('case data derives from the governing document', () => {
  it('names the document it derives from, and that document exists', () => {
    expect(caseData.governing_document).toBe('docs/evaluation/HISTORICAL_REPLAY_CASE.md');
    expect(GOVERNING.length).toBeGreaterThan(100);
  });

  it('every identifier appears verbatim in the governing document', () => {
    for (const value of [
      caseData.variant,
      caseData.clinvar_vcv,
      caseData.geo_accession,
      caseData.qualifying_pmid,
    ]) {
      expect(GOVERNING, value).toContain(value);
    }
  });

  it('every date appears verbatim in the governing document', () => {
    for (const date of Object.values(caseData.dates)) {
      expect(GOVERNING, date).toContain(date);
    }
  });

  it('both honesty sentences are quoted, not paraphrased', () => {
    for (const sentence of caseData.honesty_sentences) {
      expect(GOVERNING, sentence).toContain(sentence);
    }
  });

  it('carries the start-date caveat the governing document attaches', () => {
    expect(GOVERNING).toContain(caseData.start_date_caveat);
  });
});

describe('intervals are computed, never stored', () => {
  it('stores no day counts anywhere in the case data', () => {
    const raw = JSON.stringify(caseData);
    for (const literal of ['391', '472', '575']) {
      expect(raw, literal).not.toContain(literal);
    }
  });

  it('computes the two intervals the governing document derives', () => {
    const byId = Object.fromEntries(caseData.intervals.map((i) => [i.id, i]));
    expect(intervalDays(byId.preregistered_lead_time)).toBe(472);
    expect(intervalDays(byId.publication_to_evaluator)).toBe(391);
  });

  it('computes the accession interval the narration speaks', () => {
    const byId = Object.fromEntries(caseData.intervals.map((i) => [i.id, i]));
    expect(intervalDays(byId.accession_public_to_reflection)).toBe(575);
  });

  it('agrees with the governing document on the two it derives', () => {
    expect(GOVERNING).toContain('`472` calendar days');
    expect(GOVERNING).toContain('`391` calendar days');
  });

  it('does not claim 575 is in the governing document, because it is not', () => {
    expect(GOVERNING).not.toContain('575');
    const byId = Object.fromEntries(caseData.intervals.map((i) => [i.id, i]));
    expect(byId.accession_public_to_reflection.status).toBe('not_in_governing_document');
  });

  it('refuses an unparseable date rather than rendering a wrong number', () => {
    expect(() => daysBetween('not-a-date', '2026-04-25')).toThrow(/invalid_date/);
  });
});

describe('only one interval is labelled preregistered', () => {
  it('marks exactly one, and it is the one the document designates', () => {
    const preregistered = caseData.intervals.filter((i) => i.status === 'preregistered');
    expect(preregistered).toHaveLength(1);
    expect(preregistered[0].id).toBe('preregistered_lead_time');
    expect(intervalDays(preregistered[0])).toBe(472);
  });

  it('keeps the accession interval and the preregistered one separate', () => {
    const byId = Object.fromEntries(caseData.intervals.map((i) => [i.id, i]));
    expect(byId.accession_public_to_reflection.from).not.toBe(
      byId.preregistered_lead_time.from,
    );
    expect(byId.accession_public_to_reflection.status).not.toBe('preregistered');
  });

  it('holds no headline until the claim gate rules', () => {
    expect(caseData.headline_interval_id).toBeNull();
  });
});
