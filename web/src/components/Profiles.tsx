import { keepPreviousData, useQuery } from "@tanstack/react-query";
import type { Annotations, Data, Layout, Shape } from "plotly.js";
import { useCallback, useMemo } from "react";

import { ApiError, postProfile } from "../api/client";
import type { GreekKey, ProfileRequest, ProfileResponse } from "../api/types";
import type { ChartTheme } from "../hooks/useChartTheme";
import { usePricingRequest } from "../hooks/usePrice";
import { GREEKS } from "../lib/greeks";
import { useCompare } from "../state/compare";
import { daysToExpiry, useInputs } from "../state/inputs";
import { useUi, type ProfileMetric } from "../state/ui";
import { Chart } from "./Chart";
import { Segmented } from "./Segmented";
import { MiniSelect, Toolbar, ToolbarItem, ViewNote } from "./Toolbar";

const POINTS = 101;
/** Time profiles revalue once per date: numerical methods sample fewer dates to stay responsive. */
const TIME_POINTS_NUMERICAL = 21;
const TIME_SPOT_SHIFTS = [-10, 0, 10];

const METRICS: { value: ProfileMetric; label: string }[] = [
  { value: "value", label: "Value & payoff" },
  ...(Object.keys(GREEKS) as GreekKey[]).map((k) => ({ value: k, label: GREEKS[k].label })),
];

const RANGES = [10, 20, 30, 50].map((v) => ({ value: v, label: `±${v}%` }));

/** Horizons (valuation-date rolls) shown on the spot axis. Greeks skip expiry, where they degenerate. */
function horizons(metric: ProfileMetric, days: number): number[] {
  if (days <= 0) return [0];
  const h = metric === "value" ? [0, Math.round(days / 2)] : [0, Math.round(days / 2), Math.round(0.9 * days)];
  return [...new Set(h)];
}

/** Nudge right-edge series labels apart vertically (pixel offsets) so they never overlap. */
function spreadLabels(labels: Partial<Annotations>[], range: number): void {
  const edge = labels.filter((l) => l.xanchor === "left" && typeof l.y === "number");
  const order = [...edge].sort((a, b) => (b.y as number) - (a.y as number));
  order.forEach((l, i) => {
    const prev = order[i - 1];
    if (prev && Math.abs((prev.y as number) - (l.y as number)) < 0.06 * (range || 1)) {
      l.yshift = (prev.yshift ?? 0) - 12;
    }
  });
}

function yValues(r: ProfileResponse, i: number, metric: ProfileMetric, mode: "pure" | "cash"): number[] {
  const s = r.series[i];
  if (!s) return [];
  if (metric === "value") {
    return mode === "cash" ? s.position_value : s.position_value.map((v) => (100 * v) / r.notional);
  }
  return s.greeks[mode]?.[metric] ?? [];
}

export function Profiles() {
  const { request } = usePricingRequest();
  const inputs = useInputs((s) => s.inputs);
  const days = daysToExpiry(inputs);
  const { axis, metric, rangePct } = useUi((s) => s.profile);
  const setProfile = useUi((s) => s.setProfile);
  const mode = useUi((s) => s.greekMode);
  const pinned = useCompare((s) => s.pinned);

  const makeRequest = useCallback(
    (pricing: ProfileRequest["pricing"], primaryOnly: boolean): ProfileRequest => ({
      pricing,
      axis,
      points: axis === "time" && pricing.method !== "analytic" ? TIME_POINTS_NUMERICAL : POINTS,
      greeks: metric === "value" ? [] : [metric],
      spot_range_pct: rangePct,
      horizons_days: primaryOnly ? [0] : horizons(metric, days),
      spot_shifts_pct: primaryOnly ? [0] : TIME_SPOT_SHIFTS,
    }),
    [axis, rangePct, metric, days],
  );

  const req = useMemo(() => makeRequest(request, false), [makeRequest, request]);
  const current = useQuery({
    queryKey: ["profile", req],
    queryFn: ({ signal }) => postProfile(req, signal),
    placeholderData: keepPreviousData,
    retry: false,
    enabled: axis === "spot" || days > 0,
  });
  const pinnedReq = useMemo(() => (pinned ? makeRequest(pinned.request, true) : null), [pinned, makeRequest]);
  const pinnedQuery = useQuery({
    queryKey: ["profile", pinnedReq],
    queryFn: ({ signal }) => postProfile(pinnedReq as ProfileRequest, signal),
    enabled: pinnedReq !== null && (axis === "spot" || days > 0),
    retry: false,
  });

  const r = current.data;
  const p = pinned ? pinnedQuery.data : undefined;

  const build = useCallback(
    (t: ChartTheme): { data: Data[]; layout: Partial<Layout> } => {
      if (!r) return { data: [], layout: {} };
      const unit = metric === "value" ? (mode === "cash" ? r.currency : "% notional") : (r.units[mode]?.[metric] ?? "");
      const data: Data[] = [];
      const labels: Partial<Annotations>[] = [];
      r.series.forEach((s, i) => {
        const y = yValues(r, i, metric, mode);
        const color = t.series[i % t.series.length] ?? t.fg;
        data.push({
          type: "scatter",
          mode: "lines",
          name: s.label,
          x: r.x,
          y,
          line: { color, width: 2 },
          hovertemplate: `%{y:,.4~f} ${unit}<extra>${s.label}</extra>`,
        });
        const lastX = r.x[r.x.length - 1];
        const lastY = y[y.length - 1];
        if (lastX !== undefined && lastY !== undefined && r.series.length > 1) {
          labels.push({
            x: lastX,
            y: lastY,
            text: s.label,
            showarrow: false,
            xanchor: "left",
            xshift: 6,
            font: { size: 10, color: t.fgMuted },
          });
        }
      });
      if (metric === "value" && r.payoff) {
        const payoff = mode === "cash" ? r.payoff : r.payoff.map((v) => (100 * v) / r.notional);
        data.push({
          type: "scatter",
          mode: "lines",
          name: "Payoff at expiry",
          x: r.x,
          y: payoff,
          line: { color: t.fgFaint, width: 1.5, dash: "dot" },
          hovertemplate: `%{y:,.4~f} ${unit}<extra>Payoff</extra>`,
        });
      }
      if (p) {
        data.push({
          type: "scatter",
          mode: "lines",
          name: "Pinned",
          x: p.x,
          y: yValues(p, 0, metric, mode),
          line: { color: t.series[0], width: 2, dash: "dash" },
          opacity: 0.55,
          hovertemplate: `%{y:,.4~f} ${unit}<extra>Pinned</extra>`,
        });
      }
      const all = data.flatMap((d) => ("y" in d && Array.isArray(d.y) ? (d.y as number[]) : []));
      spreadLabels(labels, Math.max(...all) - Math.min(...all));
      const shapes: Partial<Shape>[] = [];
      if (axis === "spot") {
        const vline = (x: number, dash: "solid" | "dot"): Partial<Shape> => ({
          type: "line",
          xref: "x",
          yref: "paper",
          x0: x,
          x1: x,
          y0: 0,
          y1: 1,
          line: { color: t.lineStrong, width: 1, dash },
        });
        shapes.push(vline(r.spot, "solid"), vline(r.strike, "dot"));
        // Label S and K separately unless they (nearly) coincide on this axis.
        const span = (r.x[r.x.length - 1] ?? 1) - (r.x[0] ?? 0);
        const together = Math.abs(r.spot - r.strike) < 0.03 * span;
        const top = (x: number, text: string): Partial<Annotations> => ({
          x,
          y: 1,
          yref: "paper",
          text,
          showarrow: false,
          yanchor: "bottom",
          font: { size: 10, color: t.fgMuted },
        });
        labels.push(...(together ? [top(r.spot, "S = K")] : [top(r.spot, "S"), top(r.strike, "K")]));
      }
      return {
        data,
        layout: {
          hovermode: "x unified",
          showlegend: true,
          shapes,
          annotations: labels,
          margin: { l: 8, r: r.series.length > 1 ? 72 : 8, t: 28, b: 8 },
          xaxis: {
            title: { text: axis === "spot" ? "Spot" : "Days to expiry" },
            autorange: axis === "time" ? "reversed" : true,
          },
          yaxis: { title: { text: unit } },
        },
      };
    },
    [r, p, metric, mode, axis],
  );

  const title =
    metric === "value" ? "Position value" : `${GREEKS[metric].label} (${mode === "cash" ? "cash" : "pure"})`;

  return (
    <div>
      <Toolbar>
        <Segmented
          label="Profile axis"
          size="sm"
          value={axis}
          options={[
            { value: "spot", label: "vs Spot" },
            { value: "time", label: "vs Time" },
          ]}
          onChange={(v) => {
            setProfile({ axis: v });
          }}
        />
        <ToolbarItem label="Metric">
          <MiniSelect
            label="Profile metric"
            value={metric}
            options={METRICS}
            onChange={(v) => {
              setProfile({ metric: v });
            }}
          />
        </ToolbarItem>
        {axis === "spot" && (
          <ToolbarItem label="Range">
            <MiniSelect
              label="Spot range"
              value={rangePct}
              options={RANGES}
              onChange={(v) => {
                setProfile({ rangePct: v });
              }}
            />
          </ToolbarItem>
        )}
      </Toolbar>
      <section className="rounded-lg border border-line bg-surface p-3 shadow-card" aria-label={`${title} profile`}>
        <div className="mb-1 flex items-baseline justify-between px-1">
          <h3 className="text-[12.5px] font-medium text-fg">{title}</h3>
          {current.isFetching && <span className="text-[11px] text-fg-faint">Updating…</span>}
        </div>
        {axis === "time" && days <= 0 ? (
          <p className="px-1 py-10 text-center text-[12px] text-fg-faint">The option expires today: no time profile.</p>
        ) : current.error ? (
          <p role="alert" className="px-1 py-10 text-center text-[12px] text-neg">
            {current.error instanceof ApiError ? current.error.message : "Profile request failed."}
          </p>
        ) : (
          <Chart build={build} label={`${title} against ${axis}`} />
        )}
      </section>
      <ViewNote>
        {axis === "spot"
          ? "Full revaluation at each spot (sticky strike), after rolling the valuation date by each horizon. Vols and rates held fixed."
          : "Full revaluation as the valuation date rolls towards expiry, at the current spot and ±10%. Vols and rates held fixed."}
        {pinned && " Dashed: pinned state, current horizon only."}
      </ViewNote>
    </div>
  );
}
