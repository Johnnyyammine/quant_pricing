import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";

import { ApiError, postImpliedVol } from "../api/client";
import type { ImpliedVolRequest } from "../api/types";
import { useDebouncedValue } from "../hooks/useDebouncedValue";
import { usePricingRequest } from "../hooks/usePrice";
import { formatNumber, parseNumber } from "../lib/format";
import { useInputs } from "../state/inputs";
import { InputGroup } from "./InputGroup";
import { Tip, TipBody } from "./Tip";

/** Solve the flat implied vol reproducing a quoted unit price (Let's Be Rational). */
export function ImpliedVolGroup() {
  const [draft, setDraft] = useState("");
  const target = parseNumber(draft);
  const debouncedTarget = useDebouncedValue(target, 150);
  const { request } = usePricingRequest();
  const setInput = useInputs((s) => s.set);
  const currency = useInputs((s) => s.inputs.currency);

  const req = useMemo<ImpliedVolRequest | null>(
    () =>
      debouncedTarget !== null && debouncedTarget > 0
        ? {
            instrument: request.instrument,
            market: request.market,
            model: request.model,
            target_price: debouncedTarget,
            settings: request.settings,
          }
        : null,
    [debouncedTarget, request],
  );
  const q = useQuery({
    queryKey: ["iv", req],
    queryFn: ({ signal }) => postImpliedVol(req as ImpliedVolRequest, signal),
    enabled: req !== null,
    retry: false,
  });
  const sigmaPct = q.data ? 100 * q.data.implied_vol : null;

  return (
    <InputGroup id="implied-vol" title="Implied vol">
      <div className="grid grid-cols-[minmax(0,1fr)_132px] items-center gap-3 py-[3px]">
        <Tip
          side="right"
          content={
            <TipBody
              title="Implied volatility from price"
              definition="Flat Black vol at which the model reproduces this unit price, using the current forward and discount factor. Solved with Jäckel's Let's Be Rational (machine precision)."
              unit={`${currency} per unit`}
            />
          }
        >
          <label htmlFor="iv-target" className="text-[12px] text-fg-muted">
            Target price
          </label>
        </Tip>
        <div className="flex h-7 items-center rounded-md border border-line bg-surface pr-2 focus-within:border-accent focus-within:ring-2 focus-within:ring-[var(--focus)] hover:border-line-strong">
          <input
            id="iv-target"
            inputMode="decimal"
            autoComplete="off"
            placeholder="unit price"
            value={draft}
            onChange={(e) => {
              setDraft(e.target.value);
            }}
            className="num h-full min-w-0 flex-1 bg-transparent pl-2 text-[12.5px] text-fg outline-none placeholder:font-sans placeholder:text-fg-faint"
          />
          <span className="pl-1.5 text-[11px] text-fg-faint">{currency}</span>
        </div>
      </div>
      <div className="flex min-h-7 items-center justify-between gap-3 py-[3px]" aria-live="polite">
        <span className="text-[12px] text-fg-muted">Implied σ</span>
        {q.error ? (
          <span className="text-right text-[11.5px] text-neg">
            {q.error instanceof ApiError ? q.error.message : "Solve failed"}
          </span>
        ) : sigmaPct !== null && req ? (
          <span className="flex items-center gap-2">
            <span className="num text-[12.5px]" data-testid="implied-vol">
              {formatNumber(sigmaPct, 4)}
            </span>
            <span className="text-[11px] text-fg-faint">%</span>
            <button
              type="button"
              onClick={() => {
                setInput("volPct", sigmaPct);
              }}
              className="rounded border border-line px-1.5 py-0.5 text-[11px] text-fg-muted hover:border-line-strong hover:text-fg"
            >
              Use
            </button>
          </span>
        ) : (
          <span className="text-[12px] text-fg-faint">—</span>
        )}
      </div>
    </InputGroup>
  );
}
