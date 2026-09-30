import type { ReactNode } from "react";

import { ApiError } from "../api/client";
import { usePrice } from "../hooks/usePrice";
import { formatNumber } from "../lib/format";
import { usePin } from "../hooks/usePin";
import { PRODUCT_LABEL, useInputs } from "../state/inputs";
import { CompareBar } from "./CompareBar";

function Stat({ label, value, unit }: { label: string; value: ReactNode; unit?: string | undefined }) {
  return (
    <div className="min-w-0">
      <div className="text-[11px] text-fg-faint">{label}</div>
      <div className="flex items-baseline justify-start gap-1">
        <span className="num text-[13px] text-fg">{value}</span>
        {unit && <span className="text-[11px] text-fg-faint">{unit}</span>}
      </div>
    </div>
  );
}

export function Headline() {
  const { data, error, pending, isPending } = usePrice();
  const inputs = useInputs((s) => s.inputs);
  const r = data?.data;
  const dim = pending || !!error ? "opacity-55" : "";
  const { pinned, canPin, toggle } = usePin();

  return (
    <section
      aria-label="Result"
      className="relative overflow-hidden rounded-lg border border-line bg-surface shadow-card"
    >
      {pending && (
        <div className="absolute inset-x-0 top-0 h-[2px] overflow-hidden" aria-hidden>
          <div className="h-full w-1/3 animate-[qp-load_1.1s_ease-in-out_infinite] bg-accent" />
        </div>
      )}
      <div className="flex flex-wrap items-end justify-between gap-6 px-5 pb-4 pt-4">
        <div>
          <div className="flex items-center gap-3 text-[12px] text-fg-muted">
            <span>
              {PRODUCT_LABEL[inputs.productType]} {inputs.optionType} · K {formatNumber(inputs.strike, 2)}
              {inputs.productType === "digital" ? ` · pays ${formatNumber(inputs.payout, 2)}` : ""} · {inputs.expiry} ·{" "}
              {inputs.model === "bsm" ? `BSM (${inputs.dividendTreatment})` : "Black-76"}
            </span>
            <button
              type="button"
              onClick={toggle}
              disabled={!pinned && !canPin}
              title="Pin this result and compare subsequent changes against it (P)"
              aria-pressed={!!pinned}
              className={`rounded border px-1.5 py-px text-[11px] disabled:opacity-40 ${
                pinned
                  ? "border-accent bg-accent-soft text-fg"
                  : "border-line text-fg-muted hover:border-line-strong hover:text-fg"
              }`}
            >
              {pinned ? "Pinned" : "Pin"}
            </button>
          </div>
          <div className={`mt-1 flex items-baseline gap-2 transition-opacity ${dim}`} data-testid="headline-price">
            <span className="num text-[32px] font-medium leading-none tracking-tight">
              {r ? formatNumber(r.price, 4) : isPending ? "…" : "—"}
            </span>
            <span className="text-[13px] text-fg-muted">{r?.currency ?? inputs.currency} per unit</span>
          </div>
        </div>
        <div className={`grid grid-cols-2 gap-x-8 gap-y-2 sm:grid-cols-4 ${dim}`}>
          <Stat label="Position value" value={r ? formatNumber(r.position_value, 2) : "—"} unit={r?.currency} />
          <Stat label="% of notional" value={r ? formatNumber(r.pct_notional, 3) : "—"} unit="%" />
          <Stat label="Method" value={<span className="font-sans">{r?.diagnostics.method_label ?? "—"}</span>} />
          <Stat label="Engine CPU" value={r ? formatNumber(r.diagnostics.runtime_ms, 2) : "—"} unit="ms" />
        </div>
      </div>
      <div className={`grid grid-cols-3 gap-6 border-t border-line bg-surface-2/60 px-5 py-2.5 ${dim}`}>
        <Stat label="Forward F(0,T)" value={r ? formatNumber(r.forward, 4) : "—"} />
        <Stat label="Discount factor P(0,T)" value={r ? formatNumber(r.discount_factor, 6) : "—"} />
        <Stat label="Time to expiry τ" value={r ? formatNumber(r.time_to_expiry, 4) : "—"} unit="y ACT/365F" />
      </div>
      <CompareBar />
      {error && (
        <div role="alert" className="border-t border-line px-5 py-2 text-[12px] text-neg">
          {error instanceof ApiError ? error.message : "Pricing request failed. Is the API running?"}
        </div>
      )}
    </section>
  );
}
