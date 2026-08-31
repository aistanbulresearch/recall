# M2 staged cohort expansion

The managed cohort contains twelve synthetic institutional cases. The original
Day-1 three retain their exact logical identities, due times, and cursors; nine
new synthetic cases extend the schedule. Five new cases are linked to the five
committed, hash-verified ClinVar captures in RCL-205. No live fetch occurs.

The replay links are provenance anchors, not patient records or Recall clinical
classifications. An anchored case is displayed as
`SYNTHETIC_WITH_CAPTURED_REPLAY`; cases without an anchor are `SYNTHETIC` and
must carry `vcv = null`.

Rights boundary: NCBI ClinVar captures are retained with attribution under the
reviewed `ncbi_public_record` profile in
`docs/evaluation/HISTORICAL_REPLAY_SOURCE_MANIFEST.json`. NCBI cannot transfer
rights that may remain with submitters; terms must be re-reviewed before public
release.

Committed predictions are 3 runs on 2026-08-26, 2 on 2026-08-27, and 4 on
2026-08-28. These are predictions, not execution claims. Day-2 and later runs
must occur on their selected UTC dates.
