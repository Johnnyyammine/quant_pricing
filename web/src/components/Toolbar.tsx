import type { ReactNode } from "react";

/** One row of view controls above a chart. */
export function Toolbar({ children }: { children: ReactNode }) {
  return <div className="mb-3 flex flex-wrap items-center gap-x-5 gap-y-2">{children}</div>;
}

export function ToolbarItem({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="flex items-center gap-2 text-[12px] text-fg-muted">
      <span>{label}</span>
      {children}
    </label>
  );
}

export function MiniSelect<T extends string | number>({
  value,
  options,
  onChange,
  label,
}: {
  value: T;
  options: readonly { value: T; label: string }[];
  onChange: (v: T) => void;
  label: string;
}) {
  return (
    <select
      aria-label={label}
      value={String(value)}
      onChange={(e) => {
        const opt = options.find((o) => String(o.value) === e.target.value);
        if (opt) onChange(opt.value);
      }}
      className="h-7 rounded-md border border-line bg-surface px-2 text-[12px] text-fg outline-none hover:border-line-strong focus:border-accent"
    >
      {options.map((o) => (
        <option key={String(o.value)} value={String(o.value)}>
          {o.label}
        </option>
      ))}
    </select>
  );
}

export function ViewNote({ children }: { children: ReactNode }) {
  return <p className="mt-2 text-[11.5px] leading-relaxed text-fg-faint">{children}</p>;
}
