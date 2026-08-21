# Recall Delivery Lanes

| Lane | Branch | Worktree | Exclusive write area |
|---|---|---|---|
| L1 Platform | `feature/l1-platform` | `C:\Users\oacav\.codex\worktrees\recall-l1` | `src/recall/platform/**`, `infra/**`, `tests/platform/**` |
| L2 Core | `feature/rcl-3xx-core` | `C:\Users\oacav\OneDrive\Desktop\recall project` | Remaining `src/recall/**`, `tests/**`, `scripts/**`; only L2 may edit `pyproject.toml` or `uv.lock` |
| L3 Privacy and Demo | `feature/l3-privacy-demo` | `C:\Users\oacav\.codex\worktrees\recall-l3` | `src/recall/privacy/**`, `corpus/**`, `tests/privacy/**`, `web/**`, `docs/demo/**` |

- Integration windows: 13:00 and 21:00 Europe/Istanbul.
- Integrator: Codex in L2.
- Cloud resources and cloud mutations belong only to L1 and remain owner-gated.
- Lane branches never merge themselves into core.
- Codex merges a lane into core with `--no-ff` only when that lane's tests are green.
- Merge conflicts are returned to the lane owner for resolution.
- A lane must not write outside its exclusive area without an owner-approved lane update.
