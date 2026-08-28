/**
 * Privacy desk: what leaves the laboratory, and the proof that nothing else
 * does. Two evidence sets, both real:
 *   — the frozen P1 study (deterministic baseline vs the Gemma-assisted arm),
 *   — last night's full-cohort receipt run on the Vertex-served Gemma.
 * Every figure is a chip from the evidence-file registry; arm labels come
 * from the report itself.
 */

import { GEMMA_RUN_FIELDS, P1_FIELDS } from '../evidence-files';
import { DerivedValue, useStripEntries } from '../strip';

function chip(map: Record<string, { key: string }>, key: string) {
  return <DerivedValue entry={(map as Record<string, never>)[key]} />;
}

export function PrivacyDesk() {
  useStripEntries('privacy', [
    ...Object.values(P1_FIELDS),
    ...Object.values(GEMMA_RUN_FIELDS),
  ]);

  return (
    <section className="privacy-desk">
      <header className="view-head">
        <h1>Privacy desk</h1>
        <p className="view-sub">
          The note text never leaves the laboratory. What leaves is structured, minimized,
          hash-bound and receipted — and a local Gemma checks what the deterministic layer
          might have missed.
        </p>
      </header>

      <div className="record-grid">
        <article className="record-card">
          <h2>Frozen study: what Gemma adds</h2>
          <p className="card-note">
            180 synthetic records. The deterministic-only baseline accepts{' '}
            {chip(P1_FIELDS, 'EV-P1-BASELINE-ACCEPTED')} of{' '}
            {chip(P1_FIELDS, 'EV-P1-BASELINE-RECORDS')}; with the Gemma residual detector (arm
            labelled {chip(P1_FIELDS, 'EV-P1-ARM-B-STATUS')}) acceptance rises to{' '}
            {chip(P1_FIELDS, 'EV-P1-ARM-B-ACCEPTED')} of{' '}
            {chip(P1_FIELDS, 'EV-P1-ARM-B-RECORDS')}.
          </p>
          <p className="card-line">
            escaped identifier surfaces: baseline {chip(P1_FIELDS, 'EV-P1-ESCAPES-BASE')} · arm B{' '}
            {chip(P1_FIELDS, 'EV-P1-ESCAPES-ARM-B')}
          </p>
          <p className="card-line">
            structured-only egress: {chip(P1_FIELDS, 'EV-P1-STRUCTURED-ACCEPTED')} of{' '}
            {chip(P1_FIELDS, 'EV-P1-STRUCTURED-RECORDS')} accepted
          </p>
          <p className="card-line">
            frozen run {chip(P1_FIELDS, 'EV-P1-RUN-ID')} · protocol{' '}
            {chip(P1_FIELDS, 'EV-P1-PROTOCOL')} · report hash{' '}
            {chip(P1_FIELDS, 'EV-P1-CONTENT-HASH')}
          </p>
        </article>

        <article className="record-card">
          <h2>Full-cohort receipt run (last night)</h2>
          <p className="card-note">
            Every case in the portfolio went through the real privacy gate with the Gemma leg
            live on a private Vertex endpoint — locus declared inside each signed receipt.
          </p>
          <p className="card-line">
            receipts {chip(GEMMA_RUN_FIELDS, 'EV-GEMMA-RECEIPTS')} · duration (min){' '}
            {chip(GEMMA_RUN_FIELDS, 'EV-GEMMA-ELAPSED')} · held out{' '}
            {chip(GEMMA_RUN_FIELDS, 'EV-GEMMA-HELD-OUT')}
          </p>
          <p className="card-line">
            posture {chip(GEMMA_RUN_FIELDS, 'EV-GEMMA-POSTURE')} · locus{' '}
            {chip(GEMMA_RUN_FIELDS, 'EV-GEMMA-EXEC-LOCUS')} /{' '}
            {chip(GEMMA_RUN_FIELDS, 'EV-GEMMA-TRANSPORT')} /{' '}
            {chip(GEMMA_RUN_FIELDS, 'EV-GEMMA-LOCUS')}
          </p>
          <p className="card-line">
            model {chip(GEMMA_RUN_FIELDS, 'EV-GEMMA-MODEL')} · revision{' '}
            {chip(GEMMA_RUN_FIELDS, 'EV-GEMMA-MODEL-REV')}
          </p>
          <p className="card-line">
            receipt file {chip(GEMMA_RUN_FIELDS, 'EV-GEMMA-WIRE-SHA')} · input notes{' '}
            {chip(GEMMA_RUN_FIELDS, 'EV-GEMMA-NOTES-SHA')}
          </p>
          <p className="card-line">
            signer fingerprint {chip(GEMMA_RUN_FIELDS, 'EV-GEMMA-FINGERPRINT')} · code{' '}
            {chip(GEMMA_RUN_FIELDS, 'EV-GEMMA-COMMIT')} · dirty{' '}
            {chip(GEMMA_RUN_FIELDS, 'EV-GEMMA-DIRTY')}
          </p>
        </article>
      </div>

      <p className="honesty-footnote">
        All records are synthetic. The Gemma arm figures carry their preregistration label; the
        receipt run's signing key lives outside the repository and only its fingerprint appears
        in evidence.
      </p>
    </section>
  );
}
