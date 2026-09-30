import { keepPreviousData, useQuery } from "@tanstack/react-query";
import type { Data, Layout } from "plotly.js";
import { useCallback, useMemo } from "react";

import { ApiError, postCompare } from "../api/client";
import type { CompareResponse, GreekKey, MethodComparison } from "../api/types";
import type { ChartTheme } from "../hooks/useChartTheme";
import { usePricingRequest } from "../hooks/usePrice";
import { formatNumber } from "../lib/format";
import { GREEKS } from "../lib/greeks";
import { useInputs } from "../state/inputs";
import { Chart } from "./Chart";
import { ViewNote } from "./Toolbar";

const TABLE_GREEKS: GreekKey[] = ["delta", "gamma", "vega", "theta"];
const SHORT_LABEL: Record<string, string> = { analytic: "Analytic", lr_tree: "LR tree", cn_pde: "CN PDE" };

function greek(m: MethodComparison, key: GreekKey): number | undefined {
  return m.greeks?.find((g) => g.key === key)?.value;
}

function MethodsTable({ data, selected }: { data: CompareResponse; selected: string }) {
  const ref = data.methods.find((m) => m.method === selected && m.supported);
  return (
    <table className="w-full text-[12.5px]" data-testid="methods-table">
      <thead>
        <tr className="border-b border-line text-[11px] text-fg-faint">
          <th className="py-1.5 text-left font-normal">Method</th>
          <th className="py-1.5 pl-4 text-right font-normal">Price ({data.currency})</th>
          <th className="py-1.5 pl-4 text-right font-normal">vs selected</th>
          {TABLE_GREEKS.map((g) => (
            <th key={g} className="py-1.5 pl-4 text-right font-normal">
              {GREEKS[g].label}
            </th>
          ))}
          <th className="py-1.5 pl-4 text-right font-normal">Runtime</th>
          <th className="py-1.5 pl-3 text-left font-normal">Resolution</th>
        </tr>
      </thead>
      <tbody>
        {data.methods.map((m) =>
          m.supported && m.price != null ? (
            <tr key={m.method} className={m.method === selected ? "bg-accent-soft" : ""}>
              <td className="py-1.5 pr-2 whitespace-nowrap">{SHORT_LABEL[m.method] ?? m.label}</td>
              <td className="num py-1.5 pl-4 whitespace-nowrap">{formatNumber(m.price, 6)}</td>
              <td className="num py-1.5 pl-4 whitespace-nowrap text-fg-muted">
                {ref?.price != null && m.method !== selected
                  ? formatNumber(m.price - ref.price, 6, { sign: true })
                  : "—"}
              </td>
              {TABLE_GREEKS.map((g) => {
                const v = greek(m, g);
                return (
                  <td key={g} className="num py-1.5 pl-4 whitespace-nowrap">
                    {v === undefined ? "—" : formatNumber(v, 2)}
                  </td>
                );
              })}
              <td className="num py-1.5 pl-4 whitespace-nowrap text-fg-muted">
                {m.runtime_ms != null ? `${formatNumber(m.runtime_ms, 1)} ms` : "—"}
              </td>
              <td className="py-1.5 pl-3 text-[11.5px] whitespace-nowrap text-fg-muted">
                {m.resolution == null
                  ? "exact"
                  : m.method === "lr_tree"
                    ? `${m.resolution} steps`
                    : `${m.resolution} nodes`}
              </td>
            </tr>
          ) : (
            <tr key={m.method} className="text-fg-faint">
              <td className="py-1.5 pr-2 whitespace-nowrap">{SHORT_LABEL[m.method] ?? m.label}</td>
              <td colSpan={TABLE_GREEKS.length + 4} className="py-1.5 text-[11.5px]">
                {m.error ?? "not supported"}
              </td>
            </tr>
          ),
        )}
      </tbody>
    </table>
  );
}

export function MethodsView() {
  const { request } = usePricingRequest();
  const quantity = useInputs((s) => s.inputs.quantity);
  const strike = useInputs((s) => s.inputs.strike);
  const spot = useInputs((s) => s.inputs.spot);
  const req = useMemo(() => ({ pricing: request, convergence: true }), [request]);
  const q = useQuery({
    queryKey: ["compare", req],
    queryFn: ({ signal }) => postCompare(req, signal),
    placeholderData: keepPreviousData,
    retry: false,
  });
  const data = q.data;
  const exact = data?.methods.find((m) => m.method === "analytic" && m.supported)?.price;

  const buildConvergence = useCallback(
    (t: ChartTheme): { data: Data[]; layout: Partial<Layout> } => {
      if (!data) return { data: [], layout: {} };
      const series = data.methods.filter((m) => m.supported && (m.convergence ?? []).length > 0);
      const traces: Data[] = series.map((m, i) => ({
        type: "scatter",
        mode: "lines+markers",
        name: m.label,
        x: (m.convergence ?? []).map((p) => p.resolution),
        y: (m.convergence ?? []).map((p) => p.price),
        line: { color: t.series[i % t.series.length] ?? t.fg, width: 2 },
        marker: { size: 8 },
        customdata: (m.convergence ?? []).map((p) => p.runtime_ms),
        hovertemplate: `%{x}: %{y:.6f} (%{customdata:.1f} ms)<extra>${m.label}</extra>`,
      }));
      const shapes: Partial<Layout["shapes"][number]>[] =
        exact != null
          ? [
              {
                type: "line",
                xref: "paper",
                x0: 0,
                x1: 1,
                y0: exact,
                y1: exact,
                line: { color: t.fgFaint, width: 1, dash: "dot" },
              },
            ]
          : [];
      return {
        data: traces,
        layout: {
          showlegend: true,
          hovermode: "closest",
          shapes,
          annotations:
            exact != null
              ? [
                  {
                    xref: "paper",
                    x: 1,
                    y: exact,
                    text: "closed form",
                    showarrow: false,
                    xanchor: "right",
                    yanchor: "bottom",
                    font: { size: 10, color: t.fgMuted },
                  },
                ]
              : [],
          margin: { l: 8, r: 8, t: 28, b: 8 },
          xaxis: { type: "log", title: { text: "Resolution (tree steps / PDE space nodes)" } },
          yaxis: { title: { text: `Unit price (${data.currency})` } },
        },
      };
    },
    [data, exact],
  );

  const buildBoundary = useCallback(
    (t: ChartTheme): { data: Data[]; layout: Partial<Layout> } => {
      const b = data?.boundary;
      if (!b) return { data: [], layout: {} };
      return {
        data: [
          {
            type: "scatter",
            mode: "lines",
            name: "Exercise boundary S*",
            x: b.days,
            y: b.spot.map((v) => v ?? null),
            line: { color: t.series[0], width: 2, shape: "hv" },
            connectgaps: false,
            hovertemplate: "day %{x:.0f}: S* = %{y:.2f}<extra></extra>",
          },
        ],
        layout: {
          showlegend: false,
          margin: { l: 8, r: 8, t: 8, b: 8 },
          xaxis: { title: { text: "Days from valuation" } },
          yaxis: { title: { text: "Spot" } },
          shapes: [strike, spot].map((y, i) => ({
            type: "line",
            xref: "paper",
            x0: 0,
            x1: 1,
            y0: y,
            y1: y,
            line: { color: t.lineStrong, width: 1, dash: i === 0 ? "dot" : "solid" },
          })),
          annotations: [
            {
              xref: "paper",
              x: 0,
              y: strike,
              text: "K",
              showarrow: false,
              xanchor: "left",
              yanchor: "bottom",
              font: { size: 10, color: t.fgMuted },
            },
            {
              xref: "paper",
              x: 0,
              y: spot,
              text: "S",
              showarrow: false,
              xanchor: "left",
              yanchor: "top",
              font: { size: 10, color: t.fgMuted },
            },
          ],
        },
      };
    },
    [data, strike, spot],
  );

  if (q.error) {
    return (
      <p role="alert" className="py-10 text-center text-[12px] text-neg">
        {q.error instanceof ApiError ? q.error.message : "Comparison failed."}
      </p>
    );
  }
  if (!data) return <p className="py-10 text-center text-[12px] text-fg-faint">Comparing methods…</p>;

  const american = data.european_price != null;
  const selected = request.method;
  const selectedPrice = data.methods.find((m) => m.method === selected)?.price;

  return (
    <div className="space-y-4">
      <section className="rounded-lg border border-line bg-surface p-4 shadow-card" aria-label="Methods side by side">
        <div className="mb-2 flex items-baseline justify-between">
          <h3 className="text-[12.5px] font-medium text-fg">Methods side by side</h3>
          {q.isFetching && <span className="text-[11px] text-fg-faint">Updating…</span>}
        </div>
        <MethodsTable data={data} selected={selected} />
        {american && data.european_price != null && selectedPrice != null && (
          <div
            className="mt-3 flex flex-wrap gap-x-8 gap-y-1 border-t border-line pt-2.5 text-[12px] text-fg-muted"
            data-testid="exercise-premium"
          >
            <span>
              European (closed form) <span className="num text-fg">{formatNumber(data.european_price, 6)}</span>{" "}
              {data.currency}
            </span>
            <span>
              Early-exercise premium{" "}
              <span className="num text-fg">{formatNumber(selectedPrice - data.european_price, 6)}</span>{" "}
              {data.currency} per unit ·{" "}
              <span className="num">{formatNumber((selectedPrice - data.european_price) * quantity, 2)}</span>{" "}
              {data.currency} position
            </span>
          </div>
        )}
        <ViewNote>Greeks in cash units. Each method runs at the resolution set in Diagnostics.</ViewNote>
      </section>

      <div className={`grid gap-4 ${american ? "xl:grid-cols-2" : ""}`}>
        <section className="rounded-lg border border-line bg-surface p-3 shadow-card" aria-label="Convergence">
          <h3 className="mb-1 px-1 text-[12.5px] font-medium text-fg">Convergence</h3>
          <Chart build={buildConvergence} height={300} label="Price against numerical resolution" />
          <ViewNote>
            Unit price against resolution (PDE time steps = ¼ of space nodes).
            {exact != null
              ? " Dotted: closed form."
              : " No closed form for this product: methods converge to each other."}
          </ViewNote>
        </section>
        {american && (
          <section className="rounded-lg border border-line bg-surface p-3 shadow-card" aria-label="Exercise boundary">
            <h3 className="mb-1 px-1 text-[12.5px] font-medium text-fg">Early-exercise boundary (PDE)</h3>
            {data.boundary && data.boundary.days.length > 0 ? (
              <Chart build={buildBoundary} height={300} label="Early-exercise boundary against time" />
            ) : (
              <p className="py-10 text-center text-[12px] text-fg-faint">Early exercise is never optimal here.</p>
            )}
            <ViewNote>
              Exercise when spot is beyond S* (below for puts, above for calls), cum-dividend at ex-dates.
            </ViewNote>
          </section>
        )}
      </div>
    </div>
  );
}
