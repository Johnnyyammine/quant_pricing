import type { ReactNode } from "react";

import { usePrice } from "../hooks/usePrice";
import { formatNumber } from "../lib/format";
import { useInputs } from "../state/inputs";
import { NumericField } from "./fields";

function Card({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="rounded-lg border border-line bg-surface p-4 shadow-card">
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
          Object.entries(d.details).map(([k, v]) => (
            <Row key={k} k={k} v={typeof v === "number" ? formatNumber(v, 6) : v} />
          ))
        ) : (
          <p className="text-[12px] text-fg-faint">None reported.</p>
        )}
      </Card>
    </div>
  );
}
