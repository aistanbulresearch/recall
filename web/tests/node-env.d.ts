/**
 * Minimal ambient types for the two Node facilities the test files use at
 * runtime under vitest. The web build has no @types/node on purpose: the app
 * itself must never depend on Node, and a full type surface would let Node
 * usage creep into src/ unnoticed. These declarations are scoped to tests.
 */

declare module 'node:fs' {
  export function readFileSync(path: string, encoding: 'utf-8'): string;
}

declare const process: {
  env: Record<string, string | undefined>;
};
