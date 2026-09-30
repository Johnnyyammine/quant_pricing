import { useQuery } from "@tanstack/react-query";
import { useMemo, type ReactNode } from "react";

import { postPrice } from "../api/client";
import { usePrice } from "../hooks/usePrice";
import { formatNumber, formatSci } from "../lib/format";
import { GREEKS } from "../lib/greeks";
import { useInputs } from "../state/inputs";
import { NumericField } from "./fields";

function Card({ title, children, wide = false }: { title: string; children: ReactNode; wide?: boolean }) {
  return (
    <div className={`rounded-lg border border-line bg-surface p-4 shadow-card ${wide ? "col-span-full" : ""}`}>
      <h3 className="mb-2 text-[11px] font-semibold uppercase tracking-[0.06em] text-fg-muted">{title}</h3>
      {children}
    </div>
  );
}

function Row({ k, v, unit }: { k: string; v: ReactNode; unit?: string }) {
  return (
    <div className="flex items-baseline justify-between gap-4 py-[3px] text-[12.5px]">
      <span className="text-fg-muted">{k}</span>
      <span className="flex items-baseline gap-1">
        <span className="num">{v}</span>
        {unit && <span className="text-[11px] text-fg-faint">{unit}</span>}
      </span>
    </div>
  );
}

const DETAIL_LABELS: Record<string, { label: string; unit?: string; scale?: number; dp: number }> = {
  sigma: { label: "σ (at strike, expiry)", unit: "%", scale: 100, dp: 4 },
  forward: { label: "F(0,T)", dp: 6 },
  discount_factor: { label: "P(0,T)", dp: 8 },
  time_to_expiry_years: { label: "τ", unit: "y", dp: 6 },
  stdev: { label: "σ√T", dp: 6 },
  d1: { label: "d₁", dp: 6 },
  d2: { label: "d₂", dp: 6 },
};

/** Analytic greeks against bump-and-revalue with the same bump settings (cash units). */
function GreekCheck() {
  const { data, request } = usePrice();
  const bumpRequest = useMemo(
    () => ({ ...request, settings: { ...request.settings, force_bump_greeks: true } }),
    [request],
  );
  const bump = useQuery({
    queryKey: ["price", bumpRequest],
    queryFn: ({ signal }) => postPrice(bumpRequest, signal),
    retry: false,
  });
  const analytic = data?.data.greeks.cash ?? [];
  const bumped = new Map(bump.data?.data.greeks.cash.map((g) => [g.key, g.value]));
  // Relative differences are meaningless for greeks that vanish (e.g. vanna at d₂ = 0).
  const negligible = 1e-9 * (data?.data.notional ?? 1);
  const rows = analytic
    .filter((g) => g.source === "analytic")
    .map((g) => {
      const b = bumped.get(g.key);
      const abs = b === undefined ? undefined : Math.abs(b - g.value);
      const rel = abs === undefined || Math.abs(g.value) < negligible ? undefined : abs / Math.abs(g.value);
      return { key: g.key, unit: g.unit, a: g.value, b, abs, rel };
    });

  return (
    <Card title="Greek check · analytic vs bump" wide>
      {rows.length === 0 ? (
        <p className="text-[12px] text-fg-faint">No closed-form greeks for this method.</p>
      ) : (
        <table className="w-full text-[12px]">
          <thead>
            <tr className="text-[11px] text-fg-faint">
              <th className="pb-1 text-left font-normal">Cash</th>
              <th className="pb-1 text-right font-normal">Analytic</th>
              <th className="pb-1 text-right font-normal">Bump</th>
              <th className="pb-1 text-right font-normal">Abs. diff</th>
              <th className="pb-1 text-right font-normal">Rel. diff</th>
              <th className="pb-1 pl-3 text-left font-normal">Unit</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.key}>
                <td className="py-[2px] text-fg-muted">{GREEKS[r.key].label}</td>
                <td className="num py-[2px]">{formatNumber(r.a, 4)}</td>
                <td className="num py-[2px]">{r.b === undefined ? "…" : formatNumber(r.b, 4)}</td>
                <td className="num py-[2px] text-fg-muted">{r.abs === undefined ? "" : formatSci(r.abs, 1)}</td>
                <td className="num py-[2px] text-fg-muted">{r.rel === undefined ? "—" : formatSci(r.rel, 1)}</td>
                <td className="py-[2px] pl-3 text-[11px] text-fg-faint">{r.unit}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <p className="mt-2 text-[11px] leading-snug text-fg-faint">
        Central differences, O(h²). Differences scale with the bump sizes set above.
      </p>
    </Card>
  );
}

export function Diagnostics() {
  const { data } = usePrice();
  const bumps = useInputs((s) => s.inputs.bumps);
  const setBump = useInputs((s) => s.setBump);
  const d = data?.data.diagnostics;

  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      <Card title="Run">
        <Row k="Method" v={<span className="font-sans">{d?.method_label ?? "—"}</span>} />
        <Row k="Model" v={<span className="font-sans">{d?.model ?? "—"}</span>} />
        <Row k="Engine time" v={d ? formatNumber(d.runtime_ms, 3) : "—"} unit="ms" />
        <Row k="Round trip" v={data ? formatNumber(data.roundTripMs, 1) : "—"} unit="ms" />
        <Row k="Revaluations" v={d?.revaluations ?? "—"} />
        {d?.warnings.map((w) => (
          <p key={w} className="mt-2 text-[12px] text-warn">
            {w}
          </p>
        ))}
      </Card>
      <Card title="Bump settings">
        <NumericField
          id="bump-spot"
          label="Spot"
          value={bumps.spotRelPct}
          onChange={(v) => {
            setBump("spotRelPct", v);
          }}
          step={0.01}
          dp={3}
          min={0.0001}
          max={10}
          unit="% rel"
          help={{
            title: "Spot bump h_S / S",
            definition: "Relative spot bump for Δ, Γ, vanna, charm (central differences).",
          }}
        />
        <NumericField
          id="bump-vol"
          label="Vol"
          value={bumps.volAbsPts}
          onChange={(v) => {
            setBump("volAbsPts", v);
          }}
          step={0.01}
          dp={3}
          min={0.0001}
          max={5}
          unit="vol pt"
          help={{ title: "Vol bump h_σ", definition: "Parallel implied-vol bump for ν, volga, vanna." }}
        />
        <NumericField
          id="bump-rate"
          label="Rates"
          value={bumps.rateAbsBp}
          onChange={(v) => {
            setBump("rateAbsBp", v);
          }}
          step={0.1}
          dp={2}
          min={0.01}
          max={100}
          unit="bp"
          help={{ title: "Rate bump h_r", definition: "Parallel zero-rate bump for ρ and φ." }}
        />
        <NumericField
          id="bump-time"
          label="Time"
          value={bumps.timeDays}
          onChange={(v) => {
            setBump("timeDays", Math.round(v));
          }}
          step={1}
          dp={0}
          min={1}
          max={30}
          unit="days"
          help={{ title: "Time bump h_t", definition: "Valuation-date roll for Θ and charm, calendar days." }}
        />
      </Card>
      <Card title="Method details">
        {d && Object.keys(d.details).length ? (
          Object.entries(d.details).map(([k, v]) => {
            const meta = DETAIL_LABELS[k];
            if (typeof v !== "number") return <Row key={k} k={meta?.label ?? k} v={v} />;
            return (
              <Row
                key={k}
                k={meta?.label ?? k}
                v={formatNumber(v * (meta?.scale ?? 1), meta?.dp ?? 6)}
                {...(meta?.unit ? { unit: meta.unit } : {})}
              />
            );
          })
        ) : (
          <p className="text-[12px] text-fg-faint">None reported.</p>
        )}
      </Card>
      <GreekCheck />
    </div>
  );
}
