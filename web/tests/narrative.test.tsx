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

describe('the problem, in the locked narration terms', () => {
  it('opens with the analogy a non-specialist jury already understands', () => {
    expect(markup).toContain('You monitor dependencies for CVEs');
    expect(markup).toContain('the tools watch the changelog');
  });

  it('says what the uncertain label costs, without jargon', () => {
    expect(markup).toContain('uncertain significance');
    expect(markup).toContain('do not act, wait for evidence');
    expect(markup).toContain('cannot be used to test her relatives');
    expect(markup).toContain('a drug approved for exactly her kind of tumour');
  });

  it('keeps the evidence card on screen: every date has a source', () => {
    for (const value of [
      'VCV002895953',
      'GSE248438',
      '39779848',
      '2024-09-27',
      '2025-01-08',
      '2026-04-25',
    ]) {
      expect(markup).toContain(value);
    }
  });

  it('anchors 575 to the deposit and 472 to the publication, never as one counter', () => {
    expect(markup).toContain('575 days');
    expect(markup).toContain('472 days');
    expect(markup).toContain('Two intervals, two meanings, never one counter');
    expect(markup).toContain('nothing was watching');
  });

  it('draws the chronology to scale from the same dates it prints', () => {
    // The publication marker sits where the dates put it: 103 of the 575 days,
    // so the long stretch on the right IS the 472-day interval.
    const svg = markup.slice(markup.indexOf('Evidence chronology drawn to scale'));
    const cx = Number(svg.match(/cx="([\d.]+)"/g)![1].match(/[\d.]+/)![0]);
    expect(Math.abs(cx - (30 + (700 * 103) / 575))).toBeLessThan(0.5);
    expect(markup).toContain('the chart did not change');
  });

  it('stays short: the section is an elevator pitch, not an essay', () => {
    const section = markup.slice(
      markup.indexOf('THE PROBLEM'),
      markup.indexOf('HOW RECALL WORKS'),
    );
    const words = section.replace(/<[^>]+>/g, ' ').trim().split(/\s+/).length;
    expect(words, `problem section word count: ${words}`).toBeLessThan(330);
  });

  it('avoids unexplained clinical shorthand in the lead', () => {
    for (const jargon of ['ACMG', 'germline pathogenicity', 'cascade testing']) {
      expect(markup).not.toContain(jargon);
    }
  });
});

describe('the live run block', () => {
  it('is stamped with the run’s own clock', () => {
    expect(markup).toContain(liveRun.as_of_utc);
    expect(markup).toContain('COMPLETED');
  });

  it('never claims a clean cohort: the eight technical terminals stay visible', () => {
    for (const forbidden of ['456 successfully completed', 'all 456 cases succeeded']) {
      expect(markup.toLowerCase()).not.toContain(forbidden.toLowerCase());
    }
    expect(markup).toContain(String(liveRun.terminal_states.HALTED));
    expect(markup).toContain('stopped rather than guessed');
  });

  it('reports the run as completed, with both terminal statements', () => {
    expect(liveRun.status).toBe('COMPLETED');
    expect(markup).toContain('SUCCEEDED');
    expect(markup).toContain('INCOMPLETE');
    expect(markup).toContain('the infrastructure finished, and eight cases inside it');
  });

  it('states the cost as a projection with its verification state', () => {
    expect(liveRun.actual_billed_cost_state).toBe('NOT_VERIFIED');
    expect(markup).toContain('NOT_VERIFIED');
    expect(markup).toContain('it is a projection and is labelled as one');
  });

  it('separates rate limiting from failed cases', () => {
    expect(liveRun.governance.cases_failed_by_rate_limiting).toBe(0);
    expect(markup).toContain('without a single');
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
