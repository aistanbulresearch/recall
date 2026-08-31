/**
 * Narrative page: the claims a juror reads must stay bound to evidence.
 *
 * These tests pin the rules that make the page honest rather than persuasive:
 * the spine sentence is exact, day counts are computed from the case file, the
 * live-run block is stamped and its finals stay unclaimed, every capability
 * carries a declared verification level, the frozen measurement keeps both
 * commits and its two populations apart, and the forbidden claims never appear.
 */

import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';

import { NarrativePage } from '../src/site/NarrativePage';
import categoryFit from '../src/site/data/category-fit.json';
import liveRun from '../src/site/data/live-run.json';

const markup = renderToStaticMarkup(<NarrativePage />);

describe('the spine', () => {
  it('states the one-sentence thesis verbatim', () => {
    expect(markup).toContain(
      'A zero-trust institutional agent fleet that continuously audits changing genomic',
    );
    expect(markup).toContain('without allowing any model to become the scientific authority');
  });

  it('carries the non-clinical and synthetic frame in the masthead', () => {
    expect(markup).toContain('NON-CLINICAL RESEARCH PROTOTYPE');
    expect(markup).toContain('SYNTHETIC INSTITUTIONAL RECORDS');
    expect(markup).toContain('CAPTURED PUBLIC EVIDENCE');
  });
});

describe('the problem section', () => {
  it('computes both ruling-approved intervals from the dates', () => {
    expect(markup).toContain('575 days');
    expect(markup).toContain('472 days');
  });

  it('keeps both honesty constraints on the page', () => {
    expect(markup).toContain('conflicting, not uniformly pathogenic');
    expect(markup).toContain('does not establish that the paper caused');
    expect(markup).toContain('not a product metric');
  });
});

describe('the live run block', () => {
  it('is stamped with the instant it was read and its source', () => {
    expect(markup).toContain(liveRun.as_of_utc);
    expect(markup).toContain(liveRun.snapshot_source);
    expect(markup).toContain('RUNNING');
  });

  it('never claims a completed cohort or a final manifest', () => {
    for (const forbidden of [
      '456 successfully completed',
      'successfully completed',
      'final manifest',
      'cost reconciliation is',
    ]) {
      expect(markup.toLowerCase()).not.toContain(forbidden.toLowerCase());
    }
  });

  it('lists the finals as explicitly not claimed', () => {
    expect(markup).toContain('Not claimed yet');
    for (const item of liveRun.pending_until_terminal_evidence) {
      expect(markup).toContain(item);
    }
  });

  it('binds the run to its source commit and image digest', () => {
    expect(markup).toContain(liveRun.binding.source_commit);
    expect(markup).toContain(liveRun.binding.image_digest);
  });
});

describe('platform capability mapping', () => {
  const allowed = new Set(['LIVE VERIFIED', 'SOURCE VERIFIED', 'DEFERRED', 'NOT VERIFIED']);

  it('gives every capability a declared verification level', () => {
    expect(categoryFit.capabilities).toHaveLength(9);
    for (const row of categoryFit.capabilities) {
      expect(allowed.has(row.badge), `${row.capability}: ${row.badge}`).toBe(true);
      expect(row.limit.length, row.capability).toBeGreaterThan(0);
      expect(markup).toContain(row.capability);
    }
  });

  it('keeps Memory Bank deferred and Model Armor unattributed to the run', () => {
    const memory = categoryFit.capabilities.find((c) => c.capability === 'Memory Bank boundary')!;
    expect(memory.badge).toBe('DEFERRED');
    const armor = categoryFit.capabilities.find((c) => c.capability === 'Model Armor')!;
    expect(armor.badge).not.toBe('LIVE VERIFIED');
    expect(armor.limit).toContain('no Model Armor activity is attributed to the current run');
  });

  it('shows how a second consumer discovers the agents', () => {
    expect(markup).toContain('How a second department would find these agents');
    for (const mode of ['REGISTERED', 'MANUAL_SERVICE', 'PINNED_FALLBACK']) {
      expect(markup).toContain(mode);
    }
    expect(markup).toContain('never presented as catalogued');
  });
});

describe('authority boundary', () => {
  it('shows all three outcomes plus the technical terminal, kept apart', () => {
    for (const outcome of ['NO_ACTION', 'ABSTAIN', 'REVIEW_REQUIRED', 'HALTED']) {
      expect(markup).toContain(outcome);
    }
    expect(markup).toContain('HALTED is not a quiet ABSTAIN');
    expect(markup).toContain('Recall stopped because required proof was incomplete');
  });
});

describe('frozen measurement provenance', () => {
  it('shows both commits and never presents the measurement as current', () => {
    expect(markup).toContain('697aa6eb');
    expect(markup).toContain('63437d20');
    expect(markup).toContain('historical frozen measurement');
    expect(markup).toContain('never re-run');
  });

  it('keeps the 462 and 180 populations separate', () => {
    expect(markup).toContain('462 of 462');
    expect(markup).toContain('180');
    expect(markup).toContain('a different population from the 462');
  });
});

describe('forbidden claims', () => {
  it('never claims clinical production, diagnosis or autonomous reclassification', () => {
    for (const forbidden of [
      'clinical production',
      'diagnosis',
      'autonomous reclassification',
      'patient outcome',
    ]) {
      expect(markup.toLowerCase()).not.toContain(forbidden.toLowerCase());
    }
  });

  it('publishes no project, account or endpoint identifier', () => {
    for (const forbidden of [
      'recall-aistanbul',
      'gserviceaccount',
      'projects/',
      '9183372353592098816',
    ]) {
      expect(markup).not.toContain(forbidden);
    }
  });
});
