import { create } from "zustand";

import type { ModelType, OptionType, PriceRequest } from "../api/types";
import { addDays, addTenor, addYears, isoDate } from "../lib/dates";

export type ProductType = "european" | "american" | "digital";
export type DividendTreatment = "escrowed" | "spot";
export type CurveKey = "rate" | "dividendYield" | "borrow";

export interface Pillar {
  tenor: string;
  ratePct: number;
}

export interface CurveInput {
  mode: "flat" | "curve";
  pillars: Pillar[];
}

export interface DividendRow {
  id: number;
  exDate: string;
  cash: number;
  propPct: number;
}

export interface NumericalSettings {
  treeSteps: number;
  pdeSpaceNodes: number;
  pdeTimeSteps: number;
  digitalWidthPct: number;
  scenarioTreeSteps: number;
  scenarioPdeSpaceNodes: number;
  scenarioPdeTimeSteps: number;
}

/** Inputs in display units (rates and vols in %, bumps in desk units). */
export interface Inputs {
  productType: ProductType;
  optionType: OptionType;
  strike: number;
  expiry: string;
  quantity: number;
  currency: string;
  payout: number;
  valuationDate: string;
  spot: number;
  ratePct: number;
  dividendYieldPct: number;
  borrowPct: number;
  curves: Record<CurveKey, CurveInput>;
  dividends: DividendRow[];
  volPct: number;
  model: ModelType;
  dividendTreatment: DividendTreatment;
  method: string;
  bumps: { spotRelPct: number; volAbsPts: number; rateAbsBp: number; timeDays: number };
  numerical: NumericalSettings;
}

const FLAT_KEY: Record<CurveKey, "ratePct" | "dividendYieldPct" | "borrowPct"> = {
  rate: "ratePct",
  dividendYield: "dividendYieldPct",
  borrow: "borrowPct",
};

const DEFAULT_TENORS = ["3M", "1Y", "2Y", "5Y"];

export function defaultInputs(today: Date = new Date()): Inputs {
  const val = isoDate(today);
  const flat = (): CurveInput => ({ mode: "flat", pillars: [] });
  return {
    productType: "european",
    optionType: "call",
    strike: 100,
    expiry: addYears(val, 1),
    quantity: 10_000,
    currency: "EUR",
    payout: 1,
    valuationDate: val,
    spot: 100,
    ratePct: 3,
    dividendYieldPct: 2,
    borrowPct: 0,
    curves: { rate: flat(), dividendYield: flat(), borrow: flat() },
    dividends: [],
    volPct: 20,
    model: "bsm",
    dividendTreatment: "escrowed",
    method: "analytic",
    bumps: { spotRelPct: 0.1, volAbsPts: 0.1, rateAbsBp: 1, timeDays: 1 },
    numerical: {
      treeSteps: 401,
      pdeSpaceNodes: 800,
      pdeTimeSteps: 200,
      digitalWidthPct: 1,
      scenarioTreeSteps: 101,
      scenarioPdeSpaceNodes: 200,
      scenarioPdeTimeSteps: 100,
    },
  };
}

interface InputsStore {
  inputs: Inputs;
  set: <K extends keyof Inputs>(key: K, value: Inputs[K]) => void;
  setBump: (key: keyof Inputs["bumps"], value: number) => void;
  setNumerical: (key: keyof NumericalSettings, value: number) => void;
  setCurveMode: (key: CurveKey, mode: CurveInput["mode"]) => void;
  setPillar: (key: CurveKey, index: number, patch: Partial<Pillar>) => void;
  addPillar: (key: CurveKey) => void;
  removePillar: (key: CurveKey, index: number) => void;
  addDividend: () => void;
  updateDividend: (id: number, patch: Partial<Omit<DividendRow, "id">>) => void;
  removeDividend: (id: number) => void;
  reset: () => void;
}

let nextDividendId = 1;

export const useInputs = create<InputsStore>()((set) => {
  const update = (fn: (i: Inputs) => Partial<Inputs>) => {
    set((s) => ({ inputs: { ...s.inputs, ...fn(s.inputs) } }));
  };
  const updateCurve = (key: CurveKey, fn: (c: CurveInput) => CurveInput) => {
    update((i) => ({ curves: { ...i.curves, [key]: fn(i.curves[key]) } }));
  };
  return {
    inputs: defaultInputs(),
    set: (key, value) => {
      update(() => ({ [key]: value }));
    },
    setBump: (key, value) => {
      update((i) => ({ bumps: { ...i.bumps, [key]: value } }));
    },
    setNumerical: (key, value) => {
      update((i) => ({ numerical: { ...i.numerical, [key]: value } }));
    },
    setCurveMode: (key, mode) => {
      update((i) => {
        const c = i.curves[key];
        // Entering curve mode seeds the pillars from the flat rate.
        const pillars =
          mode === "curve" && c.pillars.length === 0
            ? DEFAULT_TENORS.map((tenor) => ({ tenor, ratePct: i[FLAT_KEY[key]] }))
            : c.pillars;
        return { curves: { ...i.curves, [key]: { mode, pillars } } };
      });
    },
    setPillar: (key, index, patch) => {
      updateCurve(key, (c) => ({ ...c, pillars: c.pillars.map((p, j) => (j === index ? { ...p, ...patch } : p)) }));
    },
    addPillar: (key) => {
      updateCurve(key, (c) => {
        const last = c.pillars[c.pillars.length - 1];
        return { ...c, pillars: [...c.pillars, { tenor: "10Y", ratePct: last?.ratePct ?? 0 }] };
      });
    },
    removePillar: (key, index) => {
      updateCurve(key, (c) => ({ ...c, pillars: c.pillars.filter((_, j) => j !== index) }));
    },
    addDividend: () => {
      update((i) => {
        const last = i.dividends[i.dividends.length - 1];
        const exDate = last ? addDays(last.exDate, 182) : addDays(i.valuationDate, 90);
        return { dividends: [...i.dividends, { id: nextDividendId++, exDate, cash: 1, propPct: 0 }] };
      });
    },
    updateDividend: (id, patch) => {
      update((i) => ({ dividends: i.dividends.map((d) => (d.id === id ? { ...d, ...patch } : d)) }));
    },
    removeDividend: (id) => {
      update((i) => ({ dividends: i.dividends.filter((d) => d.id !== id) }));
    },
    reset: () => {
      set({ inputs: defaultInputs() });
    },
  };
});

type RateIn = PriceRequest["market"]["rate"];

/** Flat decimal, or pillar curve with tenors resolved against the valuation date. */
function rateIn(i: Inputs, key: CurveKey): RateIn {
  const c = i.curves[key];
  const flat = i[FLAT_KEY[key]] / 100;
  if (c.mode === "flat") return flat;
  const pillars = c.pillars.flatMap((p) => {
    const date = addTenor(i.valuationDate, p.tenor);
    return date ? [{ date, rate: p.ratePct / 100 }] : [];
  });
  return pillars.length > 0 ? { pillars } : flat;
}

/** A request with model, method and settings always present. */
export type FullPriceRequest = PriceRequest & Required<Pick<PriceRequest, "model" | "method" | "settings">>;

/** Convert display-unit inputs to the API request (decimals). */
export function toRequest(i: Inputs): FullPriceRequest {
  const common = {
    option_type: i.optionType,
    strike: i.strike,
    expiry: i.expiry,
    quantity: i.quantity,
    currency: i.currency,
  };
  const n = i.numerical;
  return {
    instrument:
      i.productType === "digital"
        ? { type: "digital", payout: i.payout, ...common }
        : { type: i.productType, ...common },
    market: {
      valuation_date: i.valuationDate,
      spot: i.spot,
      rate: rateIn(i, "rate"),
      dividend_yield: rateIn(i, "dividendYield"),
      borrow: rateIn(i, "borrow"),
      dividends: i.dividends.map((d) => ({ ex_date: d.exDate, cash: d.cash, proportional: d.propPct / 100 })),
      vol: i.volPct / 100,
    },
    model: { type: i.model, dividend_treatment: i.dividendTreatment },
    method: i.method,
    settings: {
      bumps: {
        spot_rel: i.bumps.spotRelPct / 100,
        vol_abs: i.bumps.volAbsPts / 100,
        rate_abs: i.bumps.rateAbsBp / 1e4,
        time_days: i.bumps.timeDays,
      },
      tree: { steps: n.treeSteps },
      pde: { space_nodes: n.pdeSpaceNodes, time_steps: n.pdeTimeSteps },
      digital: { spread_width_rel: n.digitalWidthPct / 100 },
      scenario: {
        tree_steps: n.scenarioTreeSteps,
        pde_space_nodes: n.scenarioPdeSpaceNodes,
        pde_time_steps: n.scenarioPdeTimeSteps,
      },
    },
  };
}

/** Calendar days from valuation date to expiry (can be negative). */
export function daysToExpiry(i: Inputs): number {
  const ms = Date.parse(i.expiry) - Date.parse(i.valuationDate);
  return Math.round(ms / 86_400_000);
}

export const PRODUCT_LABEL: Record<ProductType, string> = {
  european: "European",
  american: "American",
  digital: "Digital",
};

function curveSummary(i: Inputs, key: CurveKey): string {
  const c = i.curves[key];
  if (c.mode === "flat") return `${i[FLAT_KEY[key]].toFixed(3)}%`;
  return c.pillars.map((p) => `${p.tenor} ${p.ratePct.toFixed(2)}%`).join(", ");
}

interface InputField {
  key: string;
  label: string;
  format: (i: Inputs) => string;
}

/** Inputs shown in the compare bar when they differ from the pinned state. */
export const COMPARED_FIELDS: InputField[] = [
  { key: "product", label: "Product", format: (i) => `${PRODUCT_LABEL[i.productType]} ${i.optionType}` },
  { key: "strike", label: "Strike", format: (i) => i.strike.toFixed(2) },
  { key: "expiry", label: "Expiry", format: (i) => i.expiry },
  { key: "quantity", label: "Qty", format: (i) => String(i.quantity) },
  { key: "payout", label: "Payout", format: (i) => (i.productType === "digital" ? i.payout.toFixed(2) : "—") },
  { key: "valuationDate", label: "Val. date", format: (i) => i.valuationDate },
  { key: "spot", label: "Spot", format: (i) => i.spot.toFixed(2) },
  { key: "rate", label: "Rate", format: (i) => curveSummary(i, "rate") },
  { key: "div", label: "Div yield", format: (i) => curveSummary(i, "dividendYield") },
  { key: "borrow", label: "Borrow", format: (i) => curveSummary(i, "borrow") },
  {
    key: "dividends",
    label: "Dividends",
    format: (i) =>
      i.dividends.length === 0 ? "none" : i.dividends.map((d) => `${d.exDate} ${d.cash}/${d.propPct}%`).join(", "),
  },
  { key: "vol", label: "Vol", format: (i) => `${i.volPct.toFixed(2)}%` },
  {
    key: "model",
    label: "Model",
    format: (i) => (i.model === "bsm" ? `BSM (${i.dividendTreatment})` : "Black-76"),
  },
  { key: "method", label: "Method", format: (i) => i.method },
];
