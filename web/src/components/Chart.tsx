import type { Config, Data, Layout } from "plotly.js";
import { useEffect, useRef, useState } from "react";

import { useChartTheme, type ChartTheme } from "../hooks/useChartTheme";

type PlotlyModule = typeof import("plotly.js");

let plotly: Promise<PlotlyModule> | null = null;
/** Plotly's cartesian partial bundle, loaded on first use so it never delays the pricer. */
function loadPlotly(): Promise<PlotlyModule> {
  plotly ??= import("plotly.js-cartesian-dist-min").then((m) => m.default);
  return plotly;
}

const CONFIG: Partial<Config> = {
  displaylogo: false,
  responsive: true,
  modeBarButtonsToRemove: ["select2d", "lasso2d", "autoScale2d", "toggleSpikelines"],
  toImageButtonOptions: { format: "png", scale: 2 },
};

function axis(t: ChartTheme) {
  return {
    gridcolor: t.line,
    linecolor: t.lineStrong,
    zerolinecolor: t.lineStrong,
    tickfont: { family: "JetBrains Mono Variable, monospace", size: 10, color: t.fgMuted },
    title: { font: { size: 11, color: t.fgMuted } },
    automargin: true,
  };
}

function baseLayout(t: ChartTheme): Partial<Layout> {
  return {
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    font: { family: "Inter Variable, sans-serif", size: 11, color: t.fgMuted },
    margin: { l: 8, r: 8, t: 8, b: 8 },
    xaxis: axis(t),
    yaxis: axis(t),
    hoverlabel: {
      bgcolor: t.surface,
      bordercolor: t.lineStrong,
      font: { family: "JetBrains Mono Variable, monospace", size: 11, color: t.fg },
    },
    legend: { orientation: "h", x: 0, y: 1.02, yanchor: "bottom", font: { color: t.fgMuted } },
  };
}

function merge(a: Partial<Layout>, b: Partial<Layout>): Partial<Layout> {
  return {
    ...a,
    ...b,
    xaxis: { ...a.xaxis, ...b.xaxis },
    yaxis: { ...a.yaxis, ...b.yaxis },
  };
}

/**
 * Plotly chart bound to the design tokens. `layout` is merged over the themed base layout;
 * `build` receives the current theme so traces can use token colours.
 */
export function Chart({
  build,
  height = 340,
  label,
}: {
  build: (t: ChartTheme) => { data: Data[]; layout?: Partial<Layout> };
  height?: number;
  label: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const theme = useChartTheme();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const el = ref.current;
    const { data, layout } = build(theme);
    void loadPlotly().then((P) => {
      if (cancelled || !el) return;
      void P.react(el, data, merge(baseLayout(theme), layout ?? {}), CONFIG).then(() => {
        setReady(true);
      });
    });
    return () => {
      cancelled = true;
    };
  }, [build, theme]);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(() => {
      void loadPlotly().then((P) => {
        if (el.isConnected) {
          P.Plots.resize(el);
        }
      });
    });
    ro.observe(el);
    return () => {
      ro.disconnect();
      void loadPlotly().then((P) => {
        P.purge(el);
      });
    };
  }, []);

  return (
    <div className="relative" style={{ height }}>
      {!ready && (
        <div className="absolute inset-0 grid place-items-center text-[12px] text-fg-faint">Loading chart…</div>
      )}
      <div ref={ref} role="img" aria-label={label} data-testid="chart" className="h-full w-full" />
    </div>
  );
}
