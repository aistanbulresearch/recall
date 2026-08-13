# Security Policy

## Current status

Recall is pre-release research and hackathon software. It is not a clinical system and must not receive real patient data.

## Never submit

- patient or participant data;
- direct identifiers or token mappings;
- API keys, private keys, access tokens, cookies, or credentials;
- production host details not already public;
- raw prompts, traces, or logs containing sensitive content.

## Reporting

Report security issues privately to the repository owner rather than opening a public issue. Do not include exploitable secrets or sensitive example data in the report.

## Required controls

- local privacy gate before cloud transfer;
- least-privilege service identities;
- no agent direct-write access to authoritative storage;
- secret and history scan before every release;
- sanitized telemetry;
- synthetic public demonstrations;
- documented rollback for hosted releases.

No compliance certification, clinical safety, or production security claim is made unless a separately defined audit establishes it.
