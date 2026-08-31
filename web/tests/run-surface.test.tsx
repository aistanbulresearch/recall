/**
 * The run surface must be honest before it is impressive.
 *
 * The figures it shows come from a committed export of one completed cohort
 * execution. These tests hold the properties that make that trustworthy: the
 * shipped copies are byte-identical to the evidence they claim to be, counts
 * are recomputed rather than repeated, the closure checks on halted cases are
 * real, an infrastructure success is never presented as an application
 * success, and no identifier or credential reaches the page.
 */

import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';

import { RunSurface } from '../src/run/RunSurface';
import {
  CASE_STATES,
  STATE_LANGUAGE,
  cohort,
  distributionAgrees,
  distributionFromCases,
  execution,
  manifest,
  modes,
  readBundle,
  roleFunnel,
} from '../src/run/runBundle';

const markup = renderToStaticMarkup(<RunSurface />);
const { ready, cases, halted } = readBundle();

/** Raw bytes of every shipped data file, and the checksums that travelled with them. */
const rawData = import.meta.glob('../src/run/data/*.json', {
  query: '?raw',
  import: 'default',
  eager: true,
}) as Record<string, string>;
const rawSums = import.meta.glob('../src/run/data/SHA256SUMS.txt', {
  query: '?raw',
  import: 'default',
  eager: true,
}) as Record<string, string>;

async function sha256(text: string): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(text));
  return Array.from(new Uint8Array(digest))
    .map((byte) => byte.toString(16).padStart(2, '0'))
    .join('');
}

function sumLines(): [string, string][] {
  return Object.values(rawSums)[0]
    .trim()
    .split('\n')
    .map((line) => line.trim().split(/\s+/) as [string, string]);
}

describe('the shipped copies are the evidence they claim to be', () => {
  it('matches every checksum that travelled with the export', async () => {
    const sums = sumLines().filter(([, name]) => name.endsWith('.json'));
    expect(sums.length).toBeGreaterThan(5);
    for (const [digest, name] of sums) {
      const path = Object.keys(rawData).find((key) => key.endsWith(`/${name}`));
      expect(path, `${name} is missing from the shipped data`).toBeDefined();
      expect(await sha256(rawData[path!]), `${name} drifted from its checksum`).toBe(digest);
    }
  });

  it('ships no data file the checksums do not cover', () => {
    const covered = new Set(sumLines().map(([, name]) => name));
    for (const key of Object.keys(rawData)) {
      expect(covered.has(key.split('/').pop()!), `${key} is uncovered`).toBe(true);
    }
  });
});

describe('the surface reads the run rather than repeating it', () => {
  it('loads the export', () => {
    expect(ready).toBe(true);
    expect(cases.length).toBe(456);
    expect(new Set(cases.map((row) => row.run)).size).toBe(456);
  });

  it('recomputes the distribution from the rows, and it agrees with the run', () => {
    const counts = distributionFromCases(cases);
    expect(counts.NO_ACTION).toBe(445);
    expect(counts.ABSTAIN).toBe(3);
    expect(counts.HALTED).toBe(8);
    expect(counts.REVIEW_REQUIRED).toBe(0);
    expect(counts.NO_ACTION + counts.ABSTAIN + counts.HALTED).toBe(cases.length);
    expect(distributionAgrees(cases)).toBe(true);
  });

  it('accounts for every case in the role funnel', () => {
    const funnel = roleFunnel();
    const failures = funnel.reduce((sum, stage) => sum + stage.failed, 0);
    expect(failures).toBe(8);
    const decided = Object.values(cohort.governance_checks.policy_outcomes_seen).reduce(
      (a, b) => a + b,
      0,
    );
    // Cases entering the first stage either failed somewhere or reached the gate.
    expect(funnel[0].started).toBe(456);
    expect(decided + failures).toBe(456);
    // Each stage starts with what the previous one completed.
    expect(funnel[1].started).toBe(funnel[0].completed);
    expect(funnel[2].started).toBe(funnel[1].completed);
    expect(decided).toBe(funnel[2].completed);
  });
});

describe('containment is shown per case, not asserted', () => {
  it('closes every halted case: no decision, no task', () => {
    expect(halted.length).toBe(8);
    for (const row of halted) {
      expect(row.closure.policy_decisions, row.case).toBe(0);
      expect(row.closure.review_tasks, row.case).toBe(0);
      expect(row.failure_receipt.safe_terminal).toBe('HALTED');
      expect(row.failure_receipt.content_hash).toMatch(/^[0-9a-f]{64}$/);
      expect(row.agent_execution_receipt.technical_code).toBe('agent_timeout');
      expect(row.trace).toBeTruthy();
    }
    expect(cohort.review_tasks_in_ledger).toBe(0);
  });

  it('renders the halted reason codes and the closure claim', () => {
    expect(markup).toContain('agent_timeout');
    expect(markup).toContain('controller_failed');
    expect(markup).toContain('That is the system working, not the system breaking');
  });

  it('keeps HALTED a technical terminal, never a scientific statement', () => {
    const haltedMeaning = STATE_LANGUAGE.HALTED.meaning.toLowerCase();
    expect(haltedMeaning).toContain('technical terminal');
    expect(haltedMeaning).toContain('never a task');
    expect(STATE_LANGUAGE.ABSTAIN.meaning).not.toEqual(STATE_LANGUAGE.HALTED.meaning);
    for (const state of CASE_STATES) {
      expect(STATE_LANGUAGE[state].meaning.length).toBeGreaterThan(40);
    }
  });
});

describe('honesty about what the run does and does not prove', () => {
  it('never presents the infrastructure result as the application result', () => {
    expect(execution.terminal_state).toBe('SUCCEEDED');
    expect(manifest.status).toBe('INCOMPLETE');
    expect(markup).toContain('An infrastructure success is not an application success');
  });

  it('reports the cost as a projection, with its verification state', () => {
    expect(cohort.cost.actual_billed_cost_state).toBe('NOT_VERIFIED');
    expect(markup).toContain('NOT_VERIFIED');
    expect(markup).toContain('not presented as an invoiced amount');
  });

  it('reports the absent cohort-level receipt without inventing a hash', () => {
    expect(modes.cohort_level_receipts).toBe(0);
    expect(modes.cohort_level_absent).toBe(true);
    expect(markup).toContain('absence reported, no hash invented');
  });

  it('separates rate limiting from failed cases', () => {
    expect(cohort.rate_limiting.http_429_count).toBeGreaterThan(0);
    expect(cohort.rate_limiting.cases_failed_by_rate_limiting).toBe(0);
  });

  it('never presents the replay as live', () => {
    expect(markup).toContain('NOT LIVE');
    expect(markup.toLowerCase()).not.toContain('live now');
    expect(markup).not.toContain('streaming');
  });
});

describe('nothing identifying reaches the page', () => {
  it('publishes no raw identifier, project, account or credential', () => {
    expect(markup).not.toMatch(
      /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/,
    );
    for (const forbidden of [
      'gserviceaccount',
      'projects/',
      'recall-aistanbul',
      'Bearer ',
      'AIza',
    ]) {
      expect(markup).not.toContain(forbidden);
    }
  });

  it('keeps content hashes, which are evidence rather than identity', () => {
    expect(markup).toMatch(/[0-9a-f]{10}…/);
  });
});
