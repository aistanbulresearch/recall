# Compressed plan iteration evidence

Evidence state: `OWNER_REPORTED` for cloud actions and absence of executed
cycles; repository plan, prefix code, and hashes are directly verified.

## Abandoned unscoped-prefix iterations

Plans `93393476b4162f0cd6036048d3e5692c6ae1b91f1ede74b6911f80c56930531b`
and `05e61f4bbe3d6bb7540ecae310e3c6f9423dcae3a7933db59ef4267e84fd9226`
used `dev_recall_m2_compressed_<cycle>_<logical-date>_`. `OWNER_REPORTED`: no
cycle ran; earlier preparation bytes remain append-only in those namespaces;
they are abandoned, were not deleted or overwritten, and no accepted manifest
references them. Independent cloud inventory/read-back and mechanism proof are
`NOT VERIFIED`.

## Current isolated iteration

Plan `5f18998f11c17b8feef52f90edd9319532a36d525dbea9e9a40538425a28dfa4`
uses `dev_recall_m2_compressed_p5f18998f11c1_<cycle>_<logical-date>_`.
Preparation, preview, prefix verification, current-cycle execution, and prior
ledger reads derive the prefix through one plan-bound helper.

Current bundle SHA-256 is
`5a69eb4394f64c1e666aeb624cac3e4e312b3758a9e48f311a8cb0eef610f7dd`;
source commit is `2d8bebbe97794865f77f037dea518a39e8f75e38`. Rebuild, repoint,
preparation, preflight, trigger execution, and cycle outcomes remain
`NOT VERIFIED`.
