/**
 * The historical replay case: the measured gap between evidence appearing and
 * the record changing.
 *
 * Interval arithmetic happens HERE, at render time, from the dates in the
 * case file — the file deliberately stores no day counts, so a displayed
 * number can never disagree with the dates beside it. Display obeys the
 * 2026-08-25 claim-gate ruling recorded in the file: the registry-chronology
 * interval may headline only while the preregistered lead-time interval is
 * labelled beside it, and both carry their own claim basis.
 */

import { HERO_CASE_FIELDS, historicalCase } from '../evidence-files';
import { DerivedValue, useStripEntries } from '../strip';

interface Interval {
  id: string;
  from: string;
  to: string;
  label: string;
  status: string;
  claim_basis: string;
}

interface HeroFile {
  dates: Record<string, string>;
  intervals: Interval[];
  honesty_sentences: string[];
  headline_interval_id: string;
  headline_requires_interval_id: string;
  governing_document: string;
}

const hero = historicalCase as unknown as HeroFile;

function daysBetween(fromIso: string, toIso: string): number {
  const ms = Date.parse(`${toIso}T00:00:00Z`) - Date.parse(`${fromIso}T00:00:00Z`);
  return Math.round(ms / 86_400_000);
}

export function HeroCase() {
  useStripEntries('hero', Object.values(HERO_CASE_FIELDS));

  const headline = hero.intervals.find((i) => i.id === hero.headline_interval_id)!;
  const required = hero.intervals.find((i) => i.id === hero.headline_requires_interval_id)!;
  const headlineDays = daysBetween(hero.dates[headline.from], hero.dates[headline.to]);
  const requiredDays = daysBetween(hero.dates[required.from], hero.dates[required.to]);

  const milestones = [
    { key: 'EV-HERO-DATE-DATA', date: hero.dates.geo_public, title: 'Data deposit public', detail: HERO_CASE_FIELDS['EV-HERO-GEO'] },
    { key: 'EV-HERO-DATE-PAPER', date: hero.dates.qualifying_publication, title: 'Qualifying publication', detail: HERO_CASE_FIELDS['EV-HERO-PMID'] },
    { key: 'EV-HERO-DATE-CLINVAR', date: hero.dates.clinvar_v5_public, title: 'ClinVar record reflects it', detail: HERO_CASE_FIELDS['EV-HERO-VCV'] },
  ];

  return (
    <section className="hero-case">
      <a className="crumb" href="#/worklist">
        ← Worklist
      </a>
      <header className="view-head">
        <h1>
          {String(HERO_CASE_FIELDS['EV-HERO-GENE'].value)}{' '}
          <DerivedValue entry={HERO_CASE_FIELDS['EV-HERO-VARIANT']} className="title-chip" />
        </h1>
        <p className="view-sub">
          The case Recall replays: how long decisive evidence sat in public view before the
          record it should have changed actually changed.
        </p>
      </header>

      <div className="chronology" role="img" aria-label="Evidence chronology">
        {milestones.map((m, index) => (
          <div className="milestone" key={m.key}>
            <span className="milestone-date">
              <DerivedValue entry={HERO_CASE_FIELDS[m.key]} />
            </span>
            <span className="milestone-dot" data-step={index + 1} />
            <span className="milestone-title">{m.title}</span>
            <span className="milestone-detail">
              <DerivedValue entry={m.detail} />
            </span>
          </div>
        ))}
        <div className="chronology-rail" />
      </div>

      <div className="interval-cards">
        <article className="interval-card headline">
          <span className="interval-days">{headlineDays} days</span>
          <span className="interval-label">{headline.label}</span>
          <span className="interval-basis">{headline.claim_basis}</span>
        </article>
        <article className="interval-card">
          <span className="interval-days">{requiredDays} days</span>
          <span className="interval-label">{required.label}</span>
          <span className="interval-basis">{required.claim_basis}</span>
        </article>
      </div>

      <div className="honesty-panel">
        {hero.honesty_sentences.map((sentence) => (
          <p key={sentence}>{sentence}</p>
        ))}
        <p className="honesty-caveat">{String(HERO_CASE_FIELDS['EV-HERO-CAVEAT'].value)}</p>
        <p className="honesty-source">
          Case chronology, not a product metric. Governed by <code>{hero.governing_document}</code>;
          day counts are computed from the dates above at render time.
        </p>
      </div>
    </section>
  );
}
