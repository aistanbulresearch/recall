# L1 platform evidence — what each artifact proves, and what it does not

Written by the lane that produced the artifacts, because the limits are the part
that gets lost when someone else assembles a package. Every row below has a
**Does not show** column on purpose: an artifact read wider than its scope is
the failure this lane spent two days finding in other people's work, and there
is no reason to assume we are immune to it.

Measured against gateway revision `recall-tool-gateway-00007-6tg`, fleet engines
in `us-central1`, on 2026-08-24/25.

---

## Gateway posture

### `gateway-posture/before-internal-ingress.json`
**Shows:** with `ingress=internal`, three different credential states from
outside the perimeter — no auth, no auth on a real path, garbage bearer — all
answered `404` in under half a second. Credentials were never evaluated.

**Does not show:** anything about the auth path. That is the point of the
artifact. The three cases are *indistinguishable*, so evidence gathered under
this posture is uninterpretable rather than weak.

**Capturable only before the flip.** Re-running it today would measure the new
posture; this file cannot be regenerated.

### `gateway-posture/after-iam-only-ingress.json`
**Shows:** same three probes, same caller, same URL, under `ingress=all` with
IAM-only enforcement: `403`, `403`, `401`. `never_200`, `never_404` and
`reasoned_refusal` true throughout, and the cases are now distinguishable from
each other.

**Does not show:** that the perimeter enforces *audience* — it does not; see the
audience finding below. It shows that refusals became reasoned and observable.

### `gateway-posture/verify-iam-only-final.json`
**Shows:** `ingress=all`, zero public principals, exactly three service-level
invokers, none missing and **none unexpected** (the check runs in both
directions), plus the inherited project-level invokers enumerated.

**Does not show:** that only three principals can call the gateway. That claim
was made by an earlier version of this gate and **was never true** —
`roles/owner` and two Google service agents carry `run.routes.invoke` at project
level regardless of the service binding. Recorded here as a corrected claim, not
quietly fixed.

---

## Negative authentication

### `gateway-negative-auth/negative-auth-run.json`
**Shows:** `no_token` → `403` and `wrong_issuer` → `401`, both refused by Cloud
Run IAM before the container, with observed reasons matching expected ones.

**Does not show:** three green rows. `all_refused` is **false** and the run exits
1, because `wrong_audience` was **not refused at the auth layer**. The
application refused it for unrelated reasons (content type, request fields), and
scoring that as an auth pass would be reason-masking.

**Two rows are NOT EXERCISED, with reasons recorded in the file:** the expired
token (a hand-crafted expired JWT fails signature validation *before* expiry is
evaluated, so it would report the wrong-issuer refusal and hide which layer
acted) and — separately — a valid capability with a wrong audience, which is
**unmeasurable by construction**: issuing a capability requires the signing key,
which exists only inside the gateway runtime.

### `gateway-negative-auth/audience-not-enforced-at-runtime.json`
**Shows:** a genuinely Google-signed ID token whose `aud` is the gcloud OAuth
client id, not this service, **passed Cloud Run and reached the container**. The
follow-up section then shows the container refusing it *itself*, on
authentication grounds — `endpoint_auth_missing`, `401`, with the `request_id`
echoed back, proving it parsed the body and then decided rather than dropping it
at the edge.

**Does not show:** a security hole. Defence in depth held. What it shows is that
the **documentation named the wrong layer**: the audience pin gives deploy-time
consistency, the perimeter admits on identity, and the *application* enforces
audience. A reader of the previous one-sentence claim would have concluded the
container's check was redundant and could be deleted safely — it is the
load-bearing one.

### `gateway-negative-auth/wrong-principal-case.json`
**Shows:** the authorization row. A token with the correct audience, from a
principal *proven* to be `recall-sa-controller` (`sub` == the service account's
`uniqueId`, recorded side by side rather than asserted in prose) and holding no
`run.invoker`, refused `403` by Cloud Run IAM before the container.

Together with the audience finding this gives the honest pair: **the perimeter
does not decide on audience, and does decide on grant.** Both measured; they
disagree; that is why both were measured.

**Also records** the temporary `tokenCreator` grant and its revocation — proven
twice, because the policy read-back reported the binding removed while
impersonation still succeeded for four more attempts. A revoked binding is not
immediately an unusable one; the policy is the intent, the behaviour is the
fact.

---

## Fleet

### `fleet-reachability/watcher-to-gateway.json`
**Shows:** verdict `CONFIG`, evidence `tool_capability_missing`. The Watcher is
the right agent (`author: evidence_watcher`), it *chose* to call
`evidence_connector`, and the call never left the process.

**Does not show:** whether an Agent Engine can reach the gateway. **Reachability
is UNANSWERED.** An earlier version of this artifact said `REACHABLE`; that was
retracted, because the classifier had concluded it from `tool_seen` plus the
absence of any recognised failure — a check reasoning from what it did not see.
The blocker is that the capability is minted by the **Controller** and seeded
into session state, so a bare `stream_query` can never reach the gateway however
healthy the network is. The chain smoke needs the Controller path.

---

## Fleet identity (no standalone artifact; recorded in commit `c84d800`)

The fleet deployed `COMPLETE` with three engines, three display names, three
service accounts, three resource ids, three catalog rows — and **one agent**,
because concurrent creates raced on a fixed staging path. Every signal checked
was metadata *about* an engine; none was testimony *from* one.

`verify_fleet_identity` now asks each engine who it is, and
`fleet_identity_is_distinct` requires both that every engine is itself and that
no two are the same. The guard returned `False/False` against the clone fleet and
`True/True` against the repaired one, unchanged, within twenty minutes — so it
has been seen to fire in both directions rather than only to pass.

---

## Standing limitations across all of the above

- **Runtime versus configuration.** These artifacts measure a running service and
  a running fleet. They say nothing about whether the code that produced them is
  present on any integrated branch; that is what the merge probe measures
  separately.
- **Instruments are not exempt.** Four checks in this lane were found reading the
  wrong surface — a guard searching a `repr`, a classifier reading silence, a
  redactor rewriting numbers inside JSON, and an acceptance criterion that passed
  as `0 == 0` on an empty set. Each was caught by running it against reality and
  reading raw output rather than the verdict. Assume the same of anything here
  that has not been seen to fail.
