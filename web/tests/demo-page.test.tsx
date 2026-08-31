/**
 * The demo page: the first thing a juror sees, and the only thing they must
 * understand to get started.
 *
 * These tests hold the two properties that make an answering interface
 * trustworthy: every answer is a projection of the committed run artifacts, and
 * a question outside them is refused rather than improvised. They also keep the
 * landing itself simple — one heading, two sentences, and a way to ask.
 */

import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';

import { DemoPage } from '../src/demo/DemoPage';
import { ANSWERS, byId, match } from '../src/demo/answers';
import { cohort, distributionFromCases, readBundle } from '../src/run/runBundle';

// Vite hands CSS through its own pipeline, so `?inline` is what yields the
// stylesheet text; `?raw` comes back empty for .css files.
const demoCss = Object.values(
  import.meta.glob('../src/demo/demo.css', { query: '?inline', import: 'default', eager: true }),
)[0] as string;

const markup = renderToStaticMarkup(<DemoPage />);
const { cases } = readBundle();
const counts = distributionFromCases(cases);

describe('the landing', () => {
  it('opens with the welcome, what Recall is, and what you can do here', () => {
    expect(markup).toContain('Welcome to the Recall demo.');
    expect(markup).toContain('zero-trust institutional agent fleet');
    expect(markup).toContain('Here you can interrogate a real run');
  });

  it('offers a way to ask before anything else is required', () => {
    expect(markup).toContain('Try asking');
    expect(markup).toContain('Ask');
    expect(markup).toContain('aria-label="Ask about the run"');
  });

  it('states that answers are not generated on demand', () => {
    expect(markup).toContain('Nothing is generated when you press Ask');
    expect(markup).toContain('refused rather than improvised');
  });

  it('keeps the non-clinical frame on the first screen', () => {
    expect(markup).toContain('NON-CLINICAL RESEARCH PROTOTYPE');
    expect(markup).toContain('SYNTHETIC RECORDS');
  });

  it('shows no run figures before a question is asked', () => {
    // The opening screen is a sentence and a prompt, not a dashboard.
    const hero = markup.slice(0, markup.indexOf('Try asking'));
    expect(hero).not.toContain(String(cohort.artifacts.documents));
    expect(hero).not.toContain('9,543');
  });
});

describe('questions route to the answer they name', () => {
  it('gives every answer a distinct id, label and keywords', () => {
    const ids = ANSWERS.map((answer) => answer.id);
    expect(new Set(ids).size).toBe(ids.length);
    for (const answer of ANSWERS) {
      expect(answer.label.length).toBeGreaterThan(8);
      expect(answer.keywords.length).toBeGreaterThan(2);
      expect(byId(answer.id)).toBe(answer);
    }
  });

  it('routes a typed question by its most specific word', () => {
    expect(match('what happens when an agent times out?')?.id).toBe('failure');
    expect(match('how much did the cohort cost')?.id).toBe('cost');
    expect(match('what leaves the laboratory')?.id).toBe('privacy');
    expect(match('why does this matter to a patient')?.id).toBe('why');
  });

  it('refuses rather than guessing when nothing matches', () => {
    expect(match('what is the weather in Istanbul')).toBeNull();
    expect(match('')).toBeNull();
  });
});

describe('answers stand on the run, not on prose', () => {
  it('reports the terminal states as the rows count them', () => {
    const runAnswer = renderToStaticMarkup(<>{byId('run')!.body}</>);
    expect(runAnswer).toContain(String(counts.NO_ACTION));
    expect(runAnswer).toContain(String(counts.ABSTAIN));
    expect(runAnswer).toContain(String(counts.HALTED));
    expect(runAnswer).toContain('SUCCEEDED');
    expect(runAnswer).toContain('INCOMPLETE');
    expect(runAnswer).toContain('an infrastructure success is not an application success');
  });

  it('proves the containment claim with the closure counts', () => {
    const failure = renderToStaticMarkup(<>{byId('failure')!.body}</>);
    expect(failure).toContain('agent_timeout');
    expect(failure).toContain('controller_failed');
    expect(failure).toContain('None of them became an action');
    expect(failure).toContain('the other 448 cases kept going');
  });

  it('answers the authority question with the gate’s own outcomes', () => {
    const authority = renderToStaticMarkup(<>{byId('authority')!.body}</>);
    expect(authority).toContain('445 NO_ACTION');
    expect(authority).toContain('3 ABSTAIN');
    expect(authority).toContain('citation_audit_incomplete');
  });

  it('keeps a dedicated answer for what cannot be proven', () => {
    const limits = renderToStaticMarkup(<>{byId('limits')!.body}</>);
    expect(limits).toContain('never verified against billing');
    expect(limits).toContain('deferred');
    expect(limits).toContain('non-clinical research prototype');
    expect(limits).toContain('the cause is tracked separately');
  });

  it('publishes no raw identifier or credential in any answer', () => {
    for (const answer of ANSWERS) {
      const body = renderToStaticMarkup(<>{answer.body}</>);
      expect(body).not.toMatch(
        /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/,
      );
      for (const forbidden of ['gserviceaccount', 'projects/', 'recall-aistanbul', 'AIza']) {
        expect(body, answer.id).not.toContain(forbidden);
      }
    }
  });
});

describe('answer layout cannot collapse its own content', () => {
  /**
   * A list item holds inline content — bold figures, code spans, links. Making
   * one a grid or flex container turns each of those into its own track, which
   * is how `agent_timeout` once rendered one letter per line. The markers are
   * positioned instead, and this guards that decision.
   */
  it('never lays out list items as grid or flex containers', () => {
    const blocks = demoCss.split('}');
    for (const block of blocks) {
      const [selector = '', body = ''] = block.split('{');
      if (!/li\s*$/.test(selector.trim())) {
        continue;
      }
      expect(body, `${selector.trim()} must not be a grid or flex container`).not.toMatch(
        /display:\s*(grid|flex)/,
      );
    }
  });

  it('keeps code spans inline so they wrap as text', () => {
    expect(demoCss).toContain('display: inline');
    expect(demoCss).toContain('overflow-wrap: anywhere');
  });

  it('sets the hero in a sans face and the conversation in mono', () => {
    expect(demoCss).toMatch(/--sans:[^;]*sans-serif/);
    expect(demoCss).toMatch(/\.demo-hero h1 \{[^}]*font-family: var\(--sans\)/);
    expect(demoCss).toMatch(/\.demo \{[^}]*font-family: var\(--mono\)/);
  });
});

describe('the questions a jury actually asks', () => {
  /**
   * Measured, not assumed. An interface that refuses most plausible questions
   * reads as broken rather than disciplined, so the routing is held to a
   * corpus of questions a judge would realistically type. Every entry must
   * reach an answer; a miss is a coverage defect, not a matter of taste.
   */
  const CORPUS = [
    'what is recall',
    'tell me about this project',
    'what technology did you use',
    'is this running on google cloud',
    'which google cloud services',
    'do you use gemini',
    'what model powers this',
    'how does the agent registry work',
    'how would another team discover these agents',
    'can another department reuse this',
    'how does it remember between scans',
    'what is persistent state',
    'does it use a memory bank',
    'how do the agents get their permissions',
    'what stops an agent doing something it should not',
    'is there a gateway',
    'how do you observe what happened',
    'can I see traces',
    'what is innovative here',
    'why is this different from a chatbot',
    'how does this scale to a hospital',
    'what happens next time it runs',
    'can I see the code',
    'how can I verify this myself',
    'who is the user',
    'is this safe for patients',
    'what about hallucinations',
    'show me the architecture',
    'how long did it take',
    'what happened when something failed',
    'how much did it cost',
    'what leaves the laboratory',
    'what cannot you prove',
    'show me one case',
    'who are the agents',
    'what did the run do',
    'why does this matter',
    'is there an audit trail',
    'how are tool calls authorized',
  ];

  it('answers every question in the corpus', () => {
    const misses = CORPUS.filter((question) => match(question) === null);
    expect(misses, `unanswered: ${misses.join(' | ')}`).toEqual([]);
  });

  it('covers each rubric capability with at least one answer', () => {
    for (const id of [
      'stack',
      'registry',
      'memory',
      'identity',
      'observability',
      'governance',
      'innovation',
      'scale',
      'verify',
      'architecture',
      'privacy',
      'authority',
      'failure',
      'limits',
    ]) {
      expect(byId(id), `no answer for ${id}`).not.toBeNull();
    }
  });

  it('tells the truth about registry resolution in this run', () => {
    const registry = renderToStaticMarkup(<>{byId('registry')!.body}</>);
    // Every resolution in this execution recorded PINNED_FALLBACK. The page
    // must not present a pinned endpoint as a catalogued one.
    expect(registry).toContain('PINNED_FALLBACK');
    expect(registry).toContain('not claimed as catalogue-resolved in this run');
  });
});
