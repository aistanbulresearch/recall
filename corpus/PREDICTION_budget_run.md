# Preregistered prediction — `num_predict` defect-fix run

- Status: **written and committed before the run it governs**
- Date: 2026-08-23
- Lane: L3
- Run identifier: `privacy-p1-dev-gemma4-budget`
- Governs: `corpus/PREREGISTRATION.md`, amendment `corpus/PREREGISTRATION_AMENDMENT_001.md`
- Change under test: `num_predict` 512 → 1024. Nothing else changes.

## 1. Why this is a defect fix and not a third iteration

The previous run recorded 24 of 72 records as `INVALID_JSON`. The cause is
measured, not inferred:

- every one of the 24 failures is a **15-span** note; every one of the 48
  successes is a **10 or 11 span** note; the separation is complete, with no
  overlap in either direction;
- a failing record returns `done_reason = length` with `eval_count = 512`,
  cut off mid-object at exactly the generation ceiling;
- the same record at a higher ceiling returns `done_reason = stop` with
  `eval_count = 578` and parses cleanly.

`num_predict = 512` therefore sits below what a complete answer for this corpus
requires. This is the same class of defect as the earlier `MAX_PROPOSALS = 8`,
which sat below the corpus floor of 10 spans per note: a budget set beneath what
the data demands, which measures the budget rather than the model.

The response-format constraint cannot repair it. A grammar constraint does not
create generation budget, and the previous run confirmed this directly: output
with and without `format: "json"` was byte-identical.

## 2. The records this prediction is about

All 24 records recorded as `INVALID_JSON` in
`artifacts/evidence/privacy-p1-dev-gemma4-json/records.jsonl`. Each carries 15
ground-truth spans. Twelve are Turkish and twelve are English.

| Turkish | English |
|---|---|
| SYNTH-TR-00108 | SYNTH-EN-00111 |
| SYNTH-TR-00114 | SYNTH-EN-00117 |
| SYNTH-TR-00120 | SYNTH-EN-00123 |
| SYNTH-TR-00126 | SYNTH-EN-00129 |
| SYNTH-TR-00132 | SYNTH-EN-00135 |
| SYNTH-TR-00138 | SYNTH-EN-00141 |
| SYNTH-TR-00144 | SYNTH-EN-00147 |
| SYNTH-TR-00150 | SYNTH-EN-00153 |
| SYNTH-TR-00156 | SYNTH-EN-00159 |
| SYNTH-TR-00162 | SYNTH-EN-00165 |
| SYNTH-TR-00168 | SYNTH-EN-00171 |
| SYNTH-TR-00174 | SYNTH-EN-00177 |

## 3. The prediction

Stated before the run, falsifiable, and scored against the run's own manifest:

1. **At least 22 of those 24 records return valid JSON** and are recorded with
   `status = OK`.
2. **Arm B incremental true positives reach at least +150**, measured against
   the deterministic baseline on the combined split. The current value is +113.
3. **Zero accepted escapes on every path** — baseline, structured-only egress,
   and the model comparison — so the mandatory safety gate reports PASS.

### Why 22 and not 24

The tolerance is for latency, not for parsing. A 15-span note needed 578 tokens
where the ceiling allowed 512, so at 1024 the ceiling stops binding. But a
longer answer takes longer to generate: the previous run's per-note latency ran
to a median of 366 s and a maximum of 532 s at three concurrent requests, against
a 900 s deadline. Notes that now generate roughly 600 to 700 tokens instead of
stopping at 512 will take proportionally longer, and one or two may cross the
deadline. A note that times out is quarantined fail-closed and counts here as
"did not parse". Two such records are tolerated; a third falsifies the
prediction.

### Why +150

The 48 records that already succeed contributed 113 incremental true positives,
about 2.35 per record. The 24 recovered records carry 15 ground-truth spans
each, of which the deterministic baseline already finds about 78 percent, leaving
roughly 3.3 residual spans per record for the model to contribute. Twenty-two
recovered records at that rate would add roughly 60 to 70, landing near +175.
The threshold is set at +150 so that the prediction asserts a real improvement
rather than restating the current value, while leaving margin for the model
contributing less on longer notes than on shorter ones.

## 4. The cost of being wrong

If any of the three clauses fails, **the Gemma arm is eliminated** under
`corpus/PREREGISTRATION.md` section 6 rule 4, and the deterministic Privacy Gate
stands alone. The structured-only egress claim does not depend on the model and
is unaffected either way.

If all three hold, **this is the last run and the configuration freezes.** No
further iteration, no further tuning, and the six bound values go to the auditor
as they stand at that moment.

## 5. What is not changing

`concurrency`, `timeout_seconds`, `num_ctx`, `num_thread`, `think`, and `format`
are untouched, as are the prompt, the adapter, the locator, the acceptance
thresholds, and all three split hashes. `num_predict` is the single variable.

## 6. Frozen split

Untouched. This prediction and this run concern the development split only.
