import { keepPreviousData, useQuery } from "@tanstack/react-query";
import type { Data, Layout } from "plotly.js";
import { useCallback, useMemo } from "react";

import { ApiError, postHeatmap } from "../api/client";
import type { HeatmapRequest, HeatmapResponse } from "../api/types";
import type { ChartTheme } from "../hooks/useChartTheme";
import { usePricingRequest } from "../hooks/usePrice";
import { useCompare } from "../state/compare";
import { daysToExpiry, useInputs } from "../state/inputs";
import { useUi } from "../state/ui";
import { Chart } from "./Chart";
import { Segmented } from "./Segmented";
import { MiniSelect, Toolbar, ToolbarItem, ViewNote } from "./Toolbar";

const SPOT_RANGES = [10, 20, 30, 50].map((v) => ({ value: v, label: `±${v}%` }));
const VOL_RANGES = [5, 10, 20].map((v) => ({ value: v, label: `±${v} pts` }));
const GRIDS = [11, 21, 41].map((v) => ({ value: v, label: `${v} × ${v}` }));
const HORIZONS = [
  { value: 0, label: "Today" },
  { value: 1, label: "+1 day" },
  { value: 7, label: "+1 week" },
  { value: 30, label: "+30 days" },
  { value: 91, label: "+91 days" },
];
/** Cell labels only when they fit. */
const MAX_LABELLED_STEPS = 11;

/** z = PnL vs base (or value difference vs pinned), null where the shock is out of domain. */
function surface(r: HeatmapResponse, pinned: HeatmapResponse | undefined, unit: "ccy" | "pct"): (number | null)[][] {
  const scale = unit === "pct" ? 100 / r.notional : 1;
  return r.values.map((row, i) =>
    row.map((v, j) => {
      if (v === null) return null;
      const ref = pinned ? pinned.values[i]?.[j] : r.base_value;
      if (ref === null || ref === undefined) return null;
      return (v - ref) * scale;
    }),
  );
}

export function Heatmap() {
  const { request } = usePricingRequest();
  const days = daysToExpiry(useInputs((s) => s.inputs));
  const settings = useUi((s) => s.heatmap);
  const setHeatmap = useUi((s) => s.setHeatmap);
  const pinned = useCompare((s) => s.pinned);
  const horizon = Math.min(settings.horizonDays, Math.max(days, 0));
  const vsPinned = settings.vsPinned && pinned !== null;

  const makeRequest = useCallback(
    (pricing: HeatmapRequest["pricing"]): HeatmapRequest => ({
      pricing,
      spot_range_pct: settings.spotRangePct,
      spot_steps: settings.steps,
      vol_range_pts: settings.volRangePts,
      vol_steps: settings.steps,
      horizon_days: horizon,
    }),
    [settings.spotRangePct, settings.steps, settings.volRangePts, horizon],
  );
  const req = useMemo(() => makeRequest(request), [makeRequest, request]);
  const current = useQuery({
    queryKey: ["heatmap", req],
    queryFn: ({ signal }) => postHeatmap(req, signal),
    placeholderData: keepPreviousData,
    retry: false,
  });
  const pinnedReq = useMemo(() => (vsPinned ? makeRequest(pinned.request) : null), [vsPinned, pinned, makeRequest]);
  const pinnedQuery = useQuery({
    queryKey: ["heatmap", pinnedReq],
    queryFn: ({ signal }) => postHeatmap(pinnedReq as HeatmapRequest, signal),
    enabled: pinnedReq !== null,
    retry: false,
  });

  const r = current.data;
  const p = vsPinned ? pinnedQuery.data : undefined;
  const unitLabel = settings.unit === "pct" ? "% notional" : (r?.currency ?? "");
  const quantity = vsPinned ? "Value − pinned" : "PnL";

  const build = useCallback(
    (t: ChartTheme): { data: Data[]; layout: Partial<Layout> } => {
      if (!r || (vsPinned && !p)) return { data: [], layout: {} };
      const z = surface(r, p, settings.unit);
      const m = Math.max(1e-12, ...z.flat().map((v) => (v === null ? 0 : Math.abs(v))));
      const dp = settings.unit === "pct" ? 2 : 0;
      const labelled = settings.steps <= MAX_LABELLED_STEPS;
      const trace = {
        type: "heatmap",
        x: r.spot_shifts_pct,
        y: r.vol_shifts_pts,
        z,
        zmin: -m,
        zmax: m,
        zmid: 0,
        colorscale: [
          [0, t.pnl.neg],
          [0.5, t.pnl.mid],
          [1, t.pnl.pos],
        ],
        xgap: 1,
        ygap: 1,
        hoverongaps: false,
        colorbar: {
          title: { text: `${quantity} (${unitLabel})`, side: "right", font: { size: 11, color: t.fgMuted } },
          thickness: 10,
          outlinewidth: 0,
          tickfont: { family: "JetBrains Mono Variable, monospace", size: 10, color: t.fgMuted },
        },
        hovertemplate: `Spot %{x:+.1f}% · Vol %{y:+.1f} pts<br>${quantity} %{z:,.${dp + 2}f} ${unitLabel}<extra></extra>`,
        ...(labelled
          ? {
              texttemplate: `%{z:,.${dp}f}`,
              textfont: { family: "JetBrains Mono Variable, monospace", size: 10, color: t.fg },
            }
          : {}),
      } as Data;
      const stepX = (r.spot_shifts_pct[1] ?? 0) - (r.spot_shifts_pct[0] ?? 0);
      const stepY = (r.vol_shifts_pts[1] ?? 0) - (r.vol_shifts_pts[0] ?? 0);
      return {
        data: [trace],
        layout: {
          margin: { l: 8, r: 8, t: 8, b: 8 },
          xaxis: { title: { text: "Spot shock (%)" }, ticksuffix: "%", zeroline: false, showgrid: false },
          yaxis: { title: { text: "Vol shock (vol pts)" }, zeroline: false, showgrid: false },
          shapes: [
            {
              type: "rect",
              x0: -stepX / 2,
              x1: stepX / 2,
              y0: -stepY / 2,
              y1: stepY / 2,
              line: { color: t.fg, width: 1.5 },
            },
          ],
        },
      };
    },
    [r, p, vsPinned, settings.unit, settings.steps, unitLabel, quantity],
  );

  const horizonOptions = HORIZONS.filter((h) => h.value <= Math.max(days, 0));

  return (
    <div>
      <Toolbar>
        <ToolbarItem label="Spot">
          <MiniSelect
            label="Spot range"
            value={settings.spotRangePct}
            options={SPOT_RANGES}
            onChange={(v) => {
              setHeatmap({ spotRangePct: v });
            }}
          />
        </ToolbarItem>
        <ToolbarItem label="Vol">
          <MiniSelect
            label="Vol range"
            value={settings.volRangePts}
            options={VOL_RANGES}
            onChange={(v) => {
              setHeatmap({ volRangePts: v });
            }}
          />
        </ToolbarItem>
        <ToolbarItem label="Grid">
          <MiniSelect
            label="Grid size"
            value={settings.steps}
            options={GRIDS}
            onChange={(v) => {
              setHeatmap({ steps: v });
            }}
          />
        </ToolbarItem>
        <ToolbarItem label="Horizon">
          <MiniSelect
            label="Horizon"
            value={horizon}
            options={horizonOptions}
            onChange={(v) => {
              setHeatmap({ horizonDays: v });
            }}
          />
        </ToolbarItem>
        <Segmented
          label="Heatmap units"
          size="sm"
          value={settings.unit}
          options={[
            { value: "ccy", label: r?.currency ?? "CCY" },
            { value: "pct", label: "% notional" },
          ]}
          onChange={(v) => {
            setHeatmap({ unit: v });
          }}
        />
        {pinned && (
          <label className="flex items-center gap-2 text-[12px] text-fg-muted">
            <input
              type="checkbox"
              checked={settings.vsPinned}
              onChange={(e) => {
                setHeatmap({ vsPinned: e.target.checked });
              }}
              className="accent-[var(--accent)]"
            />
            vs pinned
          </label>
        )}
      </Toolbar>
      <section className="rounded-lg border border-line bg-surface p-3 shadow-card" aria-label="Spot-vol heatmap">
        <div className="mb-1 flex items-baseline justify-between px-1">
          <h3 className="text-[12.5px] font-medium text-fg">
            {vsPinned ? "Value difference vs pinned" : "Full-revaluation PnL"} · spot × vol
            {horizon > 0 ? ` · after ${horizon}d` : ""}
          </h3>
          {current.isFetching && <span className="text-[11px] text-fg-faint">Updating…</span>}
        </div>
        {current.error ? (
          <p role="alert" className="px-1 py-10 text-center text-[12px] text-neg">
            {current.error instanceof ApiError ? current.error.message : "Heatmap request failed."}
          </p>
        ) : (
          <Chart build={build} height={420} label={`${quantity} over spot and vol shocks`} />
        )}
      </section>
      <ViewNote>
        {vsPinned
          ? "Each cell: current position value minus the pinned position value under the same shock."
          : "Each cell: position value under the shock minus today's value (outlined cell). Includes theta when a horizon is set."}{" "}
        Spot shocks are relative, vol shocks are parallel and absolute; blank cells are out of domain (vol ≤ 0).
      </ViewNote>
    </div>
  );
}
