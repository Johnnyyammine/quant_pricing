import { useState, type KeyboardEvent, type ReactNode } from "react";

import { formatNumber, parseNumber, roundTo } from "../lib/format";
import { Tip, TipBody } from "./Tip";

interface FieldHelp {
  title: string;
  definition: string;
  formula?: string;
}

function FieldRow({
  id,
  label,
  help,
  unit,
  wide = false,
  children,
}: {
  id: string;
  label: string;
  help?: FieldHelp | undefined;
  unit?: string | undefined;
  wide?: boolean;
  children: ReactNode;
}) {
  const text = (
    <label htmlFor={id} className="truncate text-[12px] text-fg-muted">
      {label}
    </label>
  );
  return (
    <div
      className={`grid items-center gap-3 py-[3px] ${wide ? "grid-cols-[72px_minmax(0,1fr)]" : "grid-cols-[minmax(0,1fr)_132px]"}`}
    >
      {help ? (
        <Tip side="right" content={<TipBody {...help} {...(unit ? { unit } : {})} />}>
          {text}
        </Tip>
      ) : (
        text
      )}
      {children}
    </div>
  );
}

const inputBase =
  "h-7 w-full rounded-md border bg-surface px-2 text-[12.5px] text-fg outline-none hover:border-line-strong focus:border-accent focus:ring-2 focus:ring-[var(--focus)]";

/** Bordered box holding an input and its unit side by side, so units never overlap values. */
const boxBase =
  "flex h-7 w-full items-center rounded-md border bg-surface pr-2 hover:border-line-strong focus-within:border-accent focus-within:ring-2 focus-within:ring-[var(--focus)]";

/**
 * Numeric input. Commits on every valid keystroke (the pricer is debounced downstream).
 * ↑/↓ nudge by `step`; with Shift ×10, with Alt ×0.1. Esc reverts the draft.
 */
export function NumericField({
  id,
  label,
  value,
  onChange,
  step,
  dp,
  unit,
  min,
  max,
  help,
  disabled = false,
}: {
  id: string;
  label: string;
  value: number;
  onChange: (v: number) => void;
  step: number;
  dp: number;
  unit?: string;
  min?: number;
  max?: number;
  help?: FieldHelp;
  disabled?: boolean;
}) {
  const [draft, setDraft] = useState<string | null>(null);
  const inBounds = (x: number) => (min === undefined || x >= min) && (max === undefined || x <= max);
  const parsed = draft === null ? value : parseNumber(draft);
  const invalid = draft !== null && (parsed === null || !inBounds(parsed));

  const onKey = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "ArrowUp" || e.key === "ArrowDown") {
      e.preventDefault();
      const mult = e.shiftKey ? 10 : e.altKey ? 0.1 : 1;
      const base = parsed ?? value;
      let next = roundTo(base + (e.key === "ArrowUp" ? 1 : -1) * step * mult, dp + 2);
      if (min !== undefined) next = Math.max(min, next);
      if (max !== undefined) next = Math.min(max, next);
      onChange(next);
      setDraft(null);
    } else if (e.key === "Escape") {
      setDraft(null);
    } else if (e.key === "Enter") {
      setDraft(null);
    }
  };

  return (
    <FieldRow id={id} label={label} help={help} unit={unit}>
      <div className={`${boxBase} ${invalid ? "border-neg" : "border-line"} ${disabled ? "opacity-45" : ""}`}>
        <input
          id={id}
          disabled={disabled}
          inputMode="decimal"
          autoComplete="off"
          spellCheck={false}
          aria-invalid={invalid}
          value={draft ?? formatNumber(value, dp, { group: false })}
          onChange={(e) => {
            setDraft(e.target.value);
            const x = parseNumber(e.target.value);
            if (x !== null && inBounds(x)) onChange(x);
          }}
          onBlur={() => {
            setDraft(null);
          }}
          onKeyDown={onKey}
          className="num h-full min-w-0 flex-1 bg-transparent pl-2 text-[12.5px] text-fg outline-none"
        />
        {unit && <span className="pl-1.5 text-[11px] whitespace-nowrap text-fg-faint">{unit}</span>}
      </div>
    </FieldRow>
  );
}

export function DateField({
  id,
  label,
  value,
  onChange,
  help,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (v: string) => void;
  help?: FieldHelp;
}) {
  return (
    <FieldRow id={id} label={label} help={help}>
      <input
        id={id}
        type="date"
        required
        value={value}
        onChange={(e) => {
          if (e.target.value) onChange(e.target.value);
        }}
        className={`${inputBase} num border-line`}
      />
    </FieldRow>
  );
}

export function SelectField<T extends string>({
  id,
  label,
  value,
  options,
  onChange,
  help,
  disabled,
  wide,
}: {
  id: string;
  label: string;
  value: T;
  options: readonly { value: T; label: string }[];
  onChange: (v: T) => void;
  help?: FieldHelp;
  disabled?: boolean;
  wide?: boolean;
}) {
  return (
    <FieldRow id={id} label={label} help={help} {...(wide ? { wide } : {})}>
      <select
        id={id}
        value={value}
        disabled={disabled}
        onChange={(e) => {
          onChange(e.target.value as T);
        }}
        className={`${inputBase} border-line disabled:opacity-60`}
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </FieldRow>
  );
}

export function ControlRow({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3 py-[3px]">
      <span className="text-[12px] text-fg-muted">{label}</span>
      {children}
    </div>
  );
}
