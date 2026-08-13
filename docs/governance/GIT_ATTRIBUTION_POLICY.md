# Git and GitHub Attribution Policy

## Required identity

- GitHub account: `aistanbulresearch`
- Git author name: `aistanbulresearch`
- Git committer name: `aistanbulresearch`
- Git email: the verified account email or GitHub noreply address belonging to `aistanbulresearch`

## Prohibited metadata

- `Co-authored-by` trailers
- generated-by or assistant attribution trailers
- alternate author or committer identities
- commits or pull requests created while another GitHub account is active
- signed-off or attribution lines that imply another author unless the owner explicitly authorizes them

This policy concerns repository authorship metadata. Product documentation may still accurately discuss artificial intelligence and agent architecture.

## Pre-commit gate

Before every commit:

1. read repository-local `user.name` and `user.email`;
2. confirm both belong to `aistanbulresearch`;
3. inspect the staged diff for secrets and sensitive data;
4. inspect the commit message for prohibited attribution trailers;
5. run the relevant tests and documentation checks.

## Pre-push gate

Before every push:

1. confirm the active GitHub CLI account is `aistanbulresearch`;
2. inspect all outgoing commits for author and committer identity;
3. verify no prohibited trailers exist;
4. verify the destination remote is `aistanbulresearch/recall`;
5. push without force unless the owner explicitly approves otherwise;
6. read back the remote commit identity and checks.

## Pull requests

- PRs are opened from the `aistanbulresearch` account.
- PR descriptions contain change, reason, evidence, risks, rollback, and documentation updates.
- PR templates do not contain automated authorship declarations.
- The merger verifies that the resulting commit identity and history comply with this policy.
