/**
 * House rule: no em dashes, and no en dashes standing in for them.
 *
 * The owner's decision, held here rather than in review comments so it cannot
 * drift back in one sentence at a time. Where a dash was doing work, the
 * replacement is chosen by what the sentence is doing: a colon before an
 * explanation or a list, a semicolon between independent clauses, a comma
 * around an aside.
 */

import { describe, expect, it } from 'vitest';

const EM = '—';
const EN = '–';

const sources = import.meta.glob('../src/**/*.{ts,tsx,css,json}', {
  query: '?raw',
  import: 'default',
  eager: true,
}) as Record<string, string>;

const styles = import.meta.glob('../src/**/*.css', {
  query: '?inline',
  import: 'default',
  eager: true,
}) as Record<string, string>;

describe('typography', () => {
  it('finds sources to check', () => {
    expect(Object.keys(sources).length).toBeGreaterThan(10);
  });

  it('carries no em dash or en dash in any source', () => {
    const offenders: string[] = [];
    for (const [path, text] of Object.entries({ ...sources, ...styles })) {
      if (typeof text !== 'string' || text.length === 0) {
        continue;
      }
      const em = text.split(EM).length - 1;
      const en = text.split(EN).length - 1;
      if (em + en > 0) {
        offenders.push(`${path}: ${em} em, ${en} en`);
      }
    }
    expect(offenders, offenders.join(' | ')).toEqual([]);
  });

  it('left no stray placeholder punctuation behind the replacement', () => {
    for (const [path, text] of Object.entries(sources)) {
      if (typeof text !== 'string') {
        continue;
      }
      // A missing value must read as a word, never as a lone comma.
      expect(text, path).not.toMatch(/\?\?\s*','/);
      expect(text, path).not.toMatch(/\?\?\s*',\s'/);
    }
  });
});
