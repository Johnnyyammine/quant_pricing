import type { GreekKey } from "../api/types";

export type GreekMode = "pure" | "cash";

export interface GreekMeta {
  label: string;
  symbol: string;
  definition: string;
  formula: string;
  /** Display decimals per mode. */
  dp: Record<GreekMode, number>;
}

/**
 * Tooltip content for every greek. Units are supplied by the API so they always match the
 * numbers; definitions and formulas live here. Pure = % of notional N·S; cash = position currency.
 */
export const GREEKS: Record<GreekKey, GreekMeta> = {
  delta: {
    label: "Delta",
    symbol: "Δ",
    definition: "Sensitivity to spot. Pure: % of notional. Cash: equivalent underlying position.",
    formula: "cash = ∂V/∂S · S · N",
    dp: { pure: 2, cash: 2 },
  },
  gamma: {
    label: "Gamma",
    symbol: "Γ",
    definition: "Change in delta for a 1% spot move. Pure: Δ %-points per 1%. Cash: Δ change valued at spot.",
    formula: "cash = ∂²V/∂S² · S² · N / 100",
    dp: { pure: 3, cash: 2 },
  },
  vega: {
    label: "Vega",
    symbol: "ν",
    definition: "Change in value for a +1 vol point parallel shift of the implied-vol surface.",
    formula: "cash = ∂V/∂σ · N / 100",
    dp: { pure: 3, cash: 2 },
  },
  theta: {
    label: "Theta",
    symbol: "Θ",
    definition: "Change in value over one calendar day, spot, vols and rates held fixed.",
    formula: "cash = ∂V/∂t · N / 365",
    dp: { pure: 4, cash: 2 },
  },
  rho: {
    label: "Rho",
    symbol: "ρ",
    definition: "Change in value for a +1 bp parallel shift of the discount zero curve (forward moves with r).",
    formula: "cash = ∂V/∂r · N / 10⁴",
    dp: { pure: 4, cash: 2 },
  },
  phi: {
    label: "Div rho",
    symbol: "φ",
    definition: "Change in value for a +1 bp shift of the continuous dividend yield.",
    formula: "cash = ∂V/∂q · N / 10⁴",
    dp: { pure: 4, cash: 2 },
  },
  vanna: {
    label: "Vanna",
    symbol: "∂Δ/∂σ",
    definition: "Change in delta for a +1 vol point shift.",
    formula: "cash = ∂²V/∂S∂σ · S · N / 100",
    dp: { pure: 3, cash: 2 },
  },
  volga: {
    label: "Volga",
    symbol: "∂ν/∂σ",
    definition: "Change in vega for a +1 vol point shift.",
    formula: "cash = ∂²V/∂σ² · N / 10⁴",
    dp: { pure: 4, cash: 2 },
  },
  charm: {
    label: "Charm",
    symbol: "∂Δ/∂t",
    definition: "Change in delta over one calendar day.",
    formula: "cash = ∂²V/∂S∂t · S · N / 365",
    dp: { pure: 4, cash: 2 },
  },
};
