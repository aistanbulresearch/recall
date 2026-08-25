/**
 * The evidence card, never cut.
 *
 * Every interval shown here is computed from the dates shown beside it, so a
 * number on screen cannot disagree with the dates it claims to span. Nothing is
 * hard coded: the case facts come from `historical-case.json`, which a test
 * holds to `docs/evaluation/HISTORICAL_REPLAY_CASE.md`.
 *
 * Each interval carries its own status. Only one is the preregistered
 * lead-time metric, and the card says which, because the governing document
 * says so and a viewer reading the two side by side must find the same answer.
 */

import caseData from '../data/historical-case.json';

type IntervalStatus = 'preregistered' | 'contextual' | 'not_in_governing_document';

interface CaseInterval {
  id: string;
  from: string;
  to: string;
  label: string;
  status: string;
  governing_note: string;
}

/** Whole days between two ISO dates, computed rather than stored. */
export function daysBetween(from: string, to: string): number {
  const start = Date.parse(`${from}T00:00:00Z`);
  const end = Date.parse(`${to}T00:00:00Z`);
  if (Number.isNaN(start) || Number.isNaN(end)) {
    throw new Error(`evidence_card_invalid_date:${from}..${to}`);
  }
  return Math.round((end - start) / 86_400_000);
}

export function intervalDays(interval: CaseInterval): number {
  const dates = caseData.dates as Record<string, string>;
  const from = dates[interval.from];
  const to = dates[interval.to];
  if (!from || !to) {
    throw new Error(`evidence_card_unknown_date_key:${interval.from}..${interval.to}`);
  }
  return daysBetween(from, to);
}

function statusNote(status: string): string | null {
  const table: Record<IntervalStatus, string> = {
    preregistered: 'Preregistered metric',
    contextual: 'Contextual, labelled separately',
    not_in_governing_document: 'Not the preregistered metric',
  };
  return table[status as IntervalStatus] ?? null;
}

export function EvidenceCard() {
  const intervals = caseData.intervals as CaseInterval[];
  const dates = caseData.dates as Record<string, string>;

  return (
    <section className="panel panel-evidence-card" aria-labelledby="evidence-card-heading">
      <h2 id="evidence-card-heading">Source chronology</h2>

      <dl className="case-identity">
        <div>
          <dt>Variant</dt>
          <dd>
            {caseData.gene} <code>{caseData.variant}</code>
          </dd>
        </div>
        <div>
          <dt>ClinVar</dt>
          <dd>
            <code>{caseData.clinvar_vcv}</code>
          </dd>
        </div>
        <div>
          <dt>Functional data</dt>
          <dd>
            GEO <code>{caseData.geo_accession}</code>, public {dates.geo_public}
          </dd>
        </div>
        <div>
          <dt>Paper</dt>
          <dd>
            PMID <code>{caseData.qualifying_pmid}</code>, published {dates.qualifying_publication}
          </dd>
        </div>
        <div>
          <dt>ClinVar reflection</dt>
          <dd>{dates.clinvar_v5_public}</dd>
        </div>
      </dl>

      <ul className="case-intervals">
        {intervals.map((interval) => (
          <li key={interval.id} data-interval-id={interval.id} data-status={interval.status}>
            <span className="interval-days">{intervalDays(interval)} days</span>
            <span className="interval-label">{interval.label}</span>
            {statusNote(interval.status) ? (
              <span className="interval-status">{statusNote(interval.status)}</span>
            ) : null}
          </li>
        ))}
      </ul>

      <p className="case-caveat">
        The GEO date is when the dataset accession became public. {caseData.start_date_caveat}.
      </p>

      <ul className="case-honesty">
        {caseData.honesty_sentences.map((sentence) => (
          <li key={sentence}>{sentence}</li>
        ))}
      </ul>
    </section>
  );
}
