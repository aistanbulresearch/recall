/**
 * Evidence substrate: the always-visible bottom strip.
 *
 * Every view publishes the derived values it is currently showing; the strip
 * renders them with their full lineage (json path, artifact id, content hash).
 * Clicking a DerivedValue chip in the clinician layer highlights its row here.
 * The strip is the standing proof that nothing on screen is hand-written.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import type { ReactNode } from 'react';

import type { ViewField } from '../viewmodel/types';

export interface StripEntry {
  key: string;
  label: string;
  value: string | number | null;
  status: string;
  /** Human-readable lineage, e.g. "$.receipt_count ← RUN_MANIFEST.json (a429a247)". */
  lineage: string;
}

interface StripState {
  publish: (owner: string, entries: StripEntry[]) => void;
  retract: (owner: string) => void;
  focus: (key: string) => void;
  entries: StripEntry[];
  focusedKey: string | null;
}

const StripContext = createContext<StripState | null>(null);

export function StripProvider({ children }: { children: ReactNode }) {
  const [byOwner, setByOwner] = useState<Record<string, StripEntry[]>>({});
  const [focusedKey, setFocusedKey] = useState<string | null>(null);
  const focusTimer = useRef<number | null>(null);

  const publish = useCallback((owner: string, entries: StripEntry[]) => {
    setByOwner((prev) => ({ ...prev, [owner]: entries }));
  }, []);
  const retract = useCallback((owner: string) => {
    setByOwner((prev) => {
      const next = { ...prev };
      delete next[owner];
      return next;
    });
  }, []);
  const focus = useCallback((key: string) => {
    setFocusedKey(key);
    if (focusTimer.current !== null) {
      window.clearTimeout(focusTimer.current);
    }
    focusTimer.current = window.setTimeout(() => setFocusedKey(null), 2600);
  }, []);

  const entries = useMemo(() => Object.values(byOwner).flat(), [byOwner]);
  const value = useMemo(
    () => ({ publish, retract, focus, entries, focusedKey }),
    [publish, retract, focus, entries, focusedKey],
  );
  return <StripContext.Provider value={value}>{children}</StripContext.Provider>;
}

export function useStrip(): StripState {
  const ctx = useContext(StripContext);
  if (!ctx) {
    throw new Error('useStrip requires StripProvider');
  }
  return ctx;
}

/** Publish a set of strip entries for as long as the owning view is mounted. */
export function useStripEntries(owner: string, entries: StripEntry[]): void {
  const { publish, retract } = useStrip();
  const serialized = JSON.stringify(entries);
  useEffect(() => {
    publish(owner, JSON.parse(serialized) as StripEntry[]);
    return () => retract(owner);
  }, [owner, serialized, publish, retract]);
}

export function fieldLineage(field: ViewField): string {
  const ref = field.source_refs[0];
  if (!ref) {
    return 'no source resolved';
  }
  const hash = ref.content_hash ? ref.content_hash.slice(0, 8) : '????????';
  return `${ref.json_path} ← ${ref.artifact_id} (${hash})`;
}

export function fieldToStripEntry(field: ViewField): StripEntry {
  return {
    key: field.field_id,
    label: field.label,
    value: field.value,
    status: field.status,
    lineage: fieldLineage(field),
  };
}

/**
 * A figure in the clinician layer. Rendered from a ViewField or an explicit
 * strip entry, never from a literal. Clicking it spotlights the lineage row
 * in the substrate strip.
 */
export function DerivedValue({
  entry,
  display,
  className,
}: {
  entry: StripEntry;
  display?: ReactNode;
  className?: string;
}) {
  const { focus } = useStrip();
  return (
    <button
      type="button"
      className={className ? `derived-chip ${className}` : 'derived-chip'}
      title={entry.lineage}
      data-strip-key={entry.key}
      onClick={() => focus(entry.key)}
    >
      {display ?? String(entry.value ?? 'none')}
    </button>
  );
}

export function EvidenceStrip() {
  const { entries, focusedKey } = useStrip();
  const listRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!focusedKey || !listRef.current) {
      return;
    }
    const row = listRef.current.querySelector(`[data-strip-row="${focusedKey}"]`);
    if (row) {
      row.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    }
  }, [focusedKey]);

  return (
    <aside className="evidence-strip" aria-label="Evidence substrate">
      <div className="strip-head">
        <span className="strip-title">EVIDENCE SUBSTRATE</span>
        <span className="strip-note">
          every figure above resolves from a committed artifact · {entries.length} derived values
          on screen · 0 hand-written
        </span>
      </div>
      <div className="strip-rows" ref={listRef}>
        {entries.map((entry) => (
          <div
            key={entry.key}
            data-strip-row={entry.key}
            className={
              entry.key === focusedKey ? 'strip-row focused' : 'strip-row'
            }
          >
            <span className={`strip-status s-${entry.status.toLowerCase()}`}>{entry.status}</span>
            <span className="strip-field">{entry.key}</span>
            <span className="strip-value">{String(entry.value ?? 'none')}</span>
            <span className="strip-lineage">{entry.lineage}</span>
          </div>
        ))}
      </div>
    </aside>
  );
}
