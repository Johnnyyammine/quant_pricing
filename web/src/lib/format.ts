/**
 * Number formatting. Fixed decimals per unit so columns align; true minus sign (U+2212) so
 * signed numbers keep the same width in tabular figures; negative zero prints as zero.
 */

const MINUS = "−";
const cache = new Map<string, Intl.NumberFormat>();

function formatter(dp: number, group: boolean): Intl.NumberFormat {
  const key = `${dp}|${group}`;
  let f = cache.get(key);
  if (!f) {
    f = new Intl.NumberFormat("en-US", {
      minimumFractionDigits: dp,
      maximumFractionDigits: dp,
      useGrouping: group,
    });
    cache.set(key, f);
  }
  return f;
}

export function formatNumber(x: number, dp: number, opts: { group?: boolean; sign?: boolean } = {}): string {
  if (!Number.isFinite(x)) return "—";
  const s = formatter(dp, opts.group ?? true).format(Math.abs(x));
  // Anything that rounds to zero is unsigned.
  if (/^[0.,]+$/.test(s)) return s;
  if (x < 0) return MINUS + s;
  return opts.sign ? `+${s}` : s;
}

/** Parse user input: accepts both "-" and "−", thousands separators and surrounding spaces. */
export function parseNumber(s: string): number | null {
  const cleaned = s.trim().replace(MINUS, "-").replace(/,/g, "");
  if (cleaned === "" || cleaned === "-" || cleaned === ".") return null;
  const x = Number(cleaned);
  return Number.isFinite(x) ? x : null;
}

/** Round to `dp` decimals without floating noise (used after keyboard nudges). */
export function roundTo(x: number, dp: number): number {
  const f = 10 ** dp;
  return Math.round(x * f) / f;
}
