# Preregistration Amendment 001 — primary arm promotion

- Status: **adopted 2026-08-22, before any read of the frozen test split**
- Amends: `corpus/PREREGISTRATION.md` section 4, "Two scorings of comparator B"
- Lane: L3
- Basis: the development-split measurement recorded in
  `artifacts/evidence/privacy-p1-dev-gemma4-full/p1-privacy-report.json`

## 1. What this amendment changes

Exactly one thing: **which arm is the primary scoring**.

| | before this amendment | after this amendment |
|---|---|---|
| `model_offsets` (arm A) | preregistered primary | declared secondary, still fully reported |
| `surface_exact_search` (arm B) | declared secondary, exploratory | **primary** |

Nothing else moves. Both arms continue to be measured from the same single model
call per record, adjudicated, redacted, and released by the same deterministic
code, and both continue to be published in full.

## 2. What this amendment does not change

The acceptance thresholds are **unchanged from section 6**. They are reproduced
here verbatim so that the comparison is checkable rather than asserted:

1. **Mandatory safety gate.** Zero seeded direct-identifier spans in accepted
   payloads. A single escape fails the protocol regardless of every other result.
2. The local model earns a demo claim only if it contributes at least one
   incremental true positive on the frozen test split **and** does not increase
   accepted escapes.
3. Every invalid JSON, timeout, unavailable model, or uncertain span must
   quarantine or remain blocked by the deterministic outbound gate.
4. If the model contributes no incremental true positive, increases escapes, or
   cannot complete inside the allocated privacy segment, it is removed from the
   demo critical path. The deterministic Privacy Gate stays.

The amendment changes which arm is measured against these thresholds. It does
not relax, re-derive, or restate any threshold value.

## 3. Evidence the promotion rests on

Development split, 72 records, `gemma4:e4b-it-qat`, one model call per record
scored on both arms:

| | arm A `model_offsets` | arm B `surface_exact_search` |
|---|---|---|
| incremental true positives | 0 | +113 |
| incremental false positives | +203 | +3 |
| accepted payloads | 0 of 72 | 42 of 72 |
| accepted escapes | 0 | 0 |
| exact recall | 0.782, identical to the deterministic baseline | 0.913 |

## 4. Position on the declaration timestamp

The following paragraph is the auditor's ruling, reproduced verbatim:

> Declaration commit post-dates run start by 42 minutes; working-tree history cannot independently corroborate pre-declaration. This claim is therefore NOT relied upon. The promotion's validity rests solely on (a) verified unread frozen split [manifest hash], (b) dev split's role as configuration selection, (c) full publication of both arms including Arm A's zero incremental result.

The bracketed value in clause (a) is:

- `corpus/generated/test.json` = `ef5796b16e037cb59aad2513f1ada62e1e2bef9b67cd97a9a9a7c3d53ebe8dfe`,
  byte-identical to the hash declared for the `test` split in
  `corpus/PRIVACY_CORPUS_MANIFEST.json`.

Supporting in-artifact evidence for clause (a): the recorded run carries
`split_sha256 = 05c1dc8f033fd9a90b59204cb0c4dfb23b13fd41f4bcf79e7fc9cdcfbb37bcb5`,
which is the manifest hash of the **dev** split. The artifact therefore
demonstrates from its own contents that the run read the development split and
not the frozen one.

This position claims nothing that cannot be checked. It does not assert that the
declaration existed before the run and was committed later. It states that no
such assertion is being relied on.

### Scope of the configuration-identity evidence

`adapter_version = gemma-span-adapter@1.1.0` and
`prompt_sha256 = 90108cca831ab6fbc4aca2a60969a7b4520b19061968697c24d4f2166a7dafb5`
are retained as evidence for one claim only: **that the measurement was produced
with the declared configuration.** They are not evidence of when the
configuration was declared, and they are not to be cited as such.

## 5. Values this amendment binds

The auditor approval is bound to the following six values. If any one of them
changes, the approval lapses and a new one is required:

| # | Value | Current |
|---|---|---|
| 1 | `prompt_sha256` | `90108cca831ab6fbc4aca2a60969a7b4520b19061968697c24d4f2166a7dafb5` |
| 2 | `adapter_version` and model identity | `gemma-span-adapter@1.1.0`; `registry.ollama.ai/library/gemma4@e4b-it-qat`, q4_0, file `sha256-e8b6a059ba86947a44ace84d6e5679795bc41862c25c30513142588f0e9dba1d` |
| 3 | `locator_version` and matching strategy | `surface-exact-search-locator@1.0.0`; exact substring search, ambiguity rule as declared in section 4 of the preregistration |
| 4 | acceptance thresholds | unchanged from section 6, reproduced verbatim in section 2 above |
| 5 | three split hashes | `dev` `05c1dc8f033fd9a90b59204cb0c4dfb23b13fd41f4bcf79e7fc9cdcfbb37bcb5`, `test` `ef5796b16e037cb59aad2513f1ada62e1e2bef9b67cd97a9a9a7c3d53ebe8dfe`, `train` `4f03932c103149f525f2c1d059e9b38abad359bd5604113529dc61a240d7e1a0` |
| 6 | runtime configuration | `reasoning_effort` (`think=false` on the native route), `format`, `timeout_seconds` |

Every one of these six is recorded in each evidence manifest, so a reviewer can
check the binding against the artifact rather than against this document.

## 6. Process rule adopted with this amendment

Configuration and preregistration are committed **before** the run they govern,
on every lane, without exception. A run whose governing commit does not precede
its start time is a process failure and its result is reported as such.
