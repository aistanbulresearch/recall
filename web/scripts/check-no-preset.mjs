/**
 * Static scan for preset result values in result components.
 *
 * The rule from the information architecture is that a fixture name, a preset,
 * or a literal may never determine a result-bearing value. This scan fails when
 * a component file mentions a terminal outcome, a decision enum, a fixture
 * identifier, or a bare number inside rendered text.
 */

import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';

const COMPONENT_ROOT = 'src/components';
const FORBIDDEN_RESULT_LITERALS = [
  'REVIEW_REQUIRED',
  'NO_ACTION',
  'ABSTAIN',
  'HALTED',
  'ACCEPTED',
  'QUARANTINED',
  'DENIED',
  'VERIFIED',
  'REJECTED',
  'VALIDATED',
  'PRESENT',
  'ABSENT',
  'HEALTHY',
];
const FORBIDDEN_FIXTURE_IDENTIFIERS = ['golden', 'fault', 'halted'];
const JSX_TEXT = />([^<>{}]+)</g;

function walk(directory) {
  const entries = [];
  for (const name of readdirSync(directory)) {
    const path = join(directory, name);
    if (statSync(path).isDirectory()) {
      entries.push(...walk(path));
    } else if (path.endsWith('.tsx') || path.endsWith('.ts')) {
      entries.push(path);
    }
  }
  return entries;
}

const findings = [];
for (const file of walk(COMPONENT_ROOT)) {
  const source = readFileSync(file, 'utf8');
  for (const literal of FORBIDDEN_RESULT_LITERALS) {
    if (source.includes(`'${literal}'`) || source.includes(`"${literal}"`) || source.includes(`>${literal}<`)) {
      findings.push(`${file}: result literal ${literal} is present in a result component`);
    }
  }
  for (const identifier of FORBIDDEN_FIXTURE_IDENTIFIERS) {
    if (new RegExp(`['"\`]${identifier}['"\`]`).test(source)) {
      findings.push(`${file}: fixture identifier ${identifier} is present in a result component`);
    }
  }
  for (const match of source.matchAll(JSX_TEXT)) {
    const text = match[1];
    if (/\d/.test(text) && text.trim().length > 0) {
      findings.push(`${file}: rendered text contains a numeric literal: ${JSON.stringify(text.trim())}`);
    }
  }
}

if (findings.length > 0) {
  console.error('preset-value scan FAILED');
  for (const finding of findings) {
    console.error(`  - ${finding}`);
  }
  process.exit(1);
}

console.log(`preset-value scan PASS: no preset result literal, fixture identifier, or rendered number in ${COMPONENT_ROOT}`);
