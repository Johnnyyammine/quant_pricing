import { create } from "zustand";

import type { ModelType, OptionType, PriceRequest } from "../api/types";
import { addYears, isoDate } from "../lib/dates";

/** Inputs in display units (rates and vols in %, bumps in desk units). */
export interface Inputs {
  optionType: OptionType;
  strike: number;
  expiry: string;
  quantity: number;
  currency: string;
  valuationDate: string;
  spot: number;
  ratePct: number;
  dividendYieldPct: number;
  borrowPct: number;
  volPct: number;
  model: ModelType;
  method: string;
  bumps: { spotRelPct: number; volAbsPts: number; rateAbsBp: number; timeDays: number };
}

export function defaultInputs(today: Date = new Date()): Inputs {
  const val = isoDate(today);
  return {
    optionType: "call",
    strike: 100,
    expiry: addYears(val, 1),
    quantity: 10_000,
    currency: "EUR",
    valuationDate: val,
    spot: 100,
    ratePct: 3,
    dividendYieldPct: 2,
    borrowPct: 0,
    volPct: 20,
    model: "bsm",
    method: "analytic",
    bumps: { spotRelPct: 0.1, volAbsPts: 0.1, rateAbsBp: 1, timeDays: 1 },
  };
}

interface InputsStore {
  inputs: Inputs;
  set: <K extends keyof Inputs>(key: K, value: Inputs[K]) => void;
  setBump: (key: keyof Inputs["bumps"], value: number) => void;
  reset: () => void;
}

export const useInputs = create<InputsStore>()((set) => ({
  inputs: defaultInputs(),
  set: (key, value) => {
    set((s) => ({ inputs: { ...s.inputs, [key]: value } }));
  },
  setBump: (key, value) => {
    set((s) => ({ inputs: { ...s.inputs, bumps: { ...s.inputs.bumps, [key]: value } } }));
  },
  reset: () => {
    set({ inputs: defaultInputs() });
  },
}));

/** Convert display-unit inputs to the API request (decimals). */
export function toRequest(i: Inputs): PriceRequest {
  return {
    instrument: {
      type: "european",
      option_type: i.optionType,
      strike: i.strike,
      expiry: i.expiry,
      quantity: i.quantity,
      currency: i.currency,
    },
    market: {
      valuation_date: i.valuationDate,
      spot: i.spot,
      rate: i.ratePct / 100,
      dividend_yield: i.dividendYieldPct / 100,
      borrow: i.borrowPct / 100,
      vol: i.volPct / 100,
    },
    model: { type: i.model },
    method: i.method,
    settings: {
      bumps: {
        spot_rel: i.bumps.spotRelPct / 100,
        vol_abs: i.bumps.volAbsPts / 100,
        rate_abs: i.bumps.rateAbsBp / 1e4,
        time_days: i.bumps.timeDays,
      },
      implied_vol: { max_iterations: 2 },
      force_bump_greeks: false,
    },
  };
}

/** Calendar days from valuation date to expiry (can be negative). */
export function daysToExpiry(i: Inputs): number {
  const ms = Date.parse(i.expiry) - Date.parse(i.valuationDate);
  return Math.round(ms / 86_400_000);
}

interface InputField {
  key: keyof Inputs;
  label: string;
  format: (i: Inputs) => string;
}

/** Inputs shown in the compare bar when they differ from the pinned state. */
export const COMPARED_FIELDS: InputField[] = [
  { key: "optionType", label: "Type", format: (i) => i.optionType },
  { key: "strike", label: "Strike", format: (i) => i.strike.toFixed(2) },
  { key: "expiry", label: "Expiry", format: (i) => i.expiry },
  { key: "quantity", label: "Qty", format: (i) => String(i.quantity) },
  { key: "valuationDate", label: "Val. date", format: (i) => i.valuationDate },
  { key: "spot", label: "Spot", format: (i) => i.spot.toFixed(2) },
  { key: "ratePct", label: "Rate", format: (i) => `${i.ratePct.toFixed(3)}%` },
  { key: "dividendYieldPct", label: "Div", format: (i) => `${i.dividendYieldPct.toFixed(3)}%` },
  { key: "borrowPct", label: "Borrow", format: (i) => `${i.borrowPct.toFixed(3)}%` },
  { key: "volPct", label: "Vol", format: (i) => `${i.volPct.toFixed(2)}%` },
  { key: "model", label: "Model", format: (i) => (i.model === "bsm" ? "BSM" : "Black-76") },
];
