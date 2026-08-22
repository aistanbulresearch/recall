/** Minimal deterministic resolver for the `$.a.b` and `$.a[*]` paths used by the registry. */

export type PathResult = { found: true; value: unknown } | { found: false; value: null };

export function resolvePath(source: unknown, jsonPath: string): PathResult {
  const trimmed = jsonPath.trim();
  if (!trimmed.startsWith('$')) {
    return { found: false, value: null };
  }
  const segments = trimmed
    .slice(1)
    .split('.')
    .map((segment) => segment.trim())
    .filter((segment) => segment.length > 0);

  let current: unknown = source;
  for (const segment of segments) {
    const wildcard = segment.endsWith('[*]');
    const key = wildcard ? segment.slice(0, -3) : segment;
    if (current === null || current === undefined || typeof current !== 'object') {
      return { found: false, value: null };
    }
    if (!Object.prototype.hasOwnProperty.call(current, key)) {
      return { found: false, value: null };
    }
    current = (current as Record<string, unknown>)[key];
    if (wildcard && !Array.isArray(current)) {
      return { found: false, value: null };
    }
  }
  if (current === undefined) {
    return { found: false, value: null };
  }
  return { found: true, value: current };
}
