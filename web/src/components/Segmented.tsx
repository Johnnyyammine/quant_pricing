import { useRef, type KeyboardEvent } from "react";

interface Option<T extends string> {
  value: T;
  label: string;
}

/** Radio-group style segmented control. Arrow keys move the selection. */
export function Segmented<T extends string>({
  value,
  options,
  onChange,
  label,
  size = "md",
}: {
  value: T;
  options: readonly Option<T>[];
  onChange: (v: T) => void;
  label: string;
  size?: "sm" | "md";
}) {
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  const idx = options.findIndex((o) => o.value === value);

  const onKey = (e: KeyboardEvent) => {
    const delta =
      e.key === "ArrowRight" || e.key === "ArrowDown" ? 1 : e.key === "ArrowLeft" || e.key === "ArrowUp" ? -1 : 0;
    if (!delta) return;
    e.preventDefault();
    const next = (idx + delta + options.length) % options.length;
    const opt = options[next];
    if (opt) {
      onChange(opt.value);
      refs.current[next]?.focus();
    }
  };

  const pad = size === "sm" ? "px-2 py-0.5 text-[11px]" : "px-2.5 py-1 text-[12px]";
  return (
    <div
      role="radiogroup"
      aria-label={label}
      onKeyDown={onKey}
      className="inline-flex rounded-md border border-line bg-surface-2 p-0.5"
    >
      {options.map((o, i) => {
        const active = o.value === value;
        return (
          <button
            key={o.value}
            ref={(el) => {
              refs.current[i] = el;
            }}
            type="button"
            role="radio"
            aria-checked={active}
            tabIndex={active ? 0 : -1}
            onClick={() => {
              onChange(o.value);
            }}
            className={`${pad} rounded-[5px] font-medium ${
              active ? "bg-surface text-fg shadow-card ring-1 ring-line" : "text-fg-muted hover:text-fg"
            }`}
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}
