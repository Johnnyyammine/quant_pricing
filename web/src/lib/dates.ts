/** Local calendar date as ISO yyyy-mm-dd (no timezone shift). */
export function isoDate(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function parse(iso: string): Date {
  const [y, m, d] = iso.split("-").map(Number) as [number, number, number];
  return new Date(y, m - 1, d);
}

export function addYears(iso: string, years: number): string {
  const d = parse(iso);
  return isoDate(new Date(d.getFullYear() + years, d.getMonth(), d.getDate()));
}

export function addDays(iso: string, days: number): string {
  const d = parse(iso);
  return isoDate(new Date(d.getFullYear(), d.getMonth(), d.getDate() + days));
}

const TENOR = /^\s*(\d+)\s*([dwmy])\s*$/i;

/** Normalised tenor ("3m" → "3M") or null if not of the form <n>D|W|M|Y with n > 0. */
export function normaliseTenor(tenor: string): string | null {
  const m = TENOR.exec(tenor);
  if (!m?.[1] || !m[2] || Number(m[1]) === 0) return null;
  return `${Number(m[1])}${m[2].toUpperCase()}`;
}

/** Date ``tenor`` after ``iso`` (calendar months/years; no business-day adjustment). */
export function addTenor(iso: string, tenor: string): string | null {
  const t = normaliseTenor(tenor);
  if (!t) return null;
  const n = Number(t.slice(0, -1));
  const d = parse(iso);
  switch (t.slice(-1)) {
    case "D":
      return addDays(iso, n);
    case "W":
      return addDays(iso, 7 * n);
    case "M":
      return isoDate(new Date(d.getFullYear(), d.getMonth() + n, d.getDate()));
    default:
      return isoDate(new Date(d.getFullYear() + n, d.getMonth(), d.getDate()));
  }
}
