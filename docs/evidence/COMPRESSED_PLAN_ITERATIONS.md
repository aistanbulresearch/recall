# Compressed plan iteration evidence

Evidence state: cloud outcomes below are `OWNER_REPORTED`; repository plan,
prefix code, bundle binding, local tests, and hashes are directly verified.

## Abandoned unscoped-prefix iterations

Plans `93393476b4162f0cd6036048d3e5692c6ae1b91f1ede74b6911f80c56930531b`
and `05e61f4bbe3d6bb7540ecae310e3c6f9423dcae3a7933db59ef4267e84fd9226`
used `dev_recall_m2_compressed_<cycle>_<logical-date>_`. `OWNER_REPORTED`: no
cycle ran; earlier preparation bytes remain append-only in those namespaces;
they are abandoned, were not deleted or overwritten, and no accepted manifest
references them. Independent cloud inventory/read-back and mechanism proof are
`NOT VERIFIED`.

## Plan-3 isolated iteration

Plan `5f18998f11c17b8feef52f90edd9319532a36d525dbea9e9a40538425a28dfa4`
uses `dev_recall_m2_compressed_p5f18998f11c1_<cycle>_<logical-date>_`.
Preparation, preview, prefix verification, current-cycle execution, and prior
ledger reads derive the prefix through one plan-bound helper.

The owner reports c1 completed under this plan with 3/3 predicted and manifest
ID beginning `bd51bd00`; that ledger row is immutable. The owner reports c2
missed its window because the operator layer slept. Independent cloud
read-back, exact c1 content hash, and the missed-trigger mechanism are
`NOT VERIFIED` by L2.

Plan-3 bundle SHA-256 was
`5a69eb4394f64c1e666aeb624cac3e4e312b3758a9e48f311a8cb0eef610f7dd`;
source commit is `2d8bebbe97794865f77f037dea518a39e8f75e38`. Rebuild, repoint,
preparation and preflight evidence remain outside the current L2 checkout.

## Current plan-4 iteration

Plan `4c2b5ededcf79472781d0d58eca23b46278dcd0a9cc3fcaeb8c307f7a6c84e89`
uses `dev_recall_m2_compressed_p4c2b5ededcf7_<cycle>_<logical-date>_` for
unexecuted cycles. c2 explicitly binds its predecessor to plan-3 SHA
`5f18998f11c17b8feef52f90edd9319532a36d525dbea9e9a40538425a28dfa4`,
prefix `dev_recall_m2_compressed_p5f18998f11c1_c1_20260826_`, and manifest ID
`bd51bd00-fcf4-5d91-a45d-4d203e02127c`; c1 is not copied.

Product commit is `b5cd5a815baad5980a3d62bfb49ab980b63e3057`. Bundle SHA-256 is
`4b494be9c82de3c3762ecc6249169b26922334f6e47af0010dafb163667a5f57`.
c2-c5 start 22:30/22:50/23:10/23:30Z on 2026-08-26. c6 is declared for
2026-08-27 12:00-12:29:59Z and is fail-closed behind
`FIRESTORE_BATCH_V1`. Plan-4 cloud preparation, preflight, triggers, and cycle
outcomes remain `NOT VERIFIED`.
