import { useEffect, useState } from "react";

export interface ChartTheme {
  fg: string;
  fgMuted: string;
  fgFaint: string;
  line: string;
  lineStrong: string;
  surface: string;
  series: [string, string, string, string];
  pnl: { neg: string; mid: string; pos: string };
}

function read(): ChartTheme {
  const css = getComputedStyle(document.documentElement);
  const v = (name: string) => css.getPropertyValue(name).trim();
  return {
    fg: v("--fg"),
    fgMuted: v("--fg-muted"),
    fgFaint: v("--fg-faint"),
    line: v("--line"),
    lineStrong: v("--line-strong"),
    surface: v("--surface"),
    series: [v("--series-1"), v("--series-2"), v("--series-3"), v("--series-4")],
    pnl: { neg: v("--pnl-neg"), mid: v("--pnl-mid"), pos: v("--pnl-pos") },
  };
}

/** Chart colours from the CSS tokens, re-read whenever <html data-theme> changes. */
export function useChartTheme(): ChartTheme {
  const [theme, setTheme] = useState(read);
  useEffect(() => {
    const observer = new MutationObserver(() => {
      setTheme(read());
    });
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    return () => {
      observer.disconnect();
    };
  }, []);
  return theme;
}
