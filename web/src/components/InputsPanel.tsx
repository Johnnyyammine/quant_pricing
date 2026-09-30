import { useEffect } from "react";

import { useMeta } from "../hooks/usePrice";
import { useInputs, type ProductType } from "../state/inputs";
import { DividendsGroup } from "./DividendsGroup";
import { ControlRow, DateField, NumericField, SelectField } from "./fields";
import { ImpliedVolGroup } from "./ImpliedVolGroup";
import { InputGroup } from "./InputGroup";
import { RateField } from "./RateField";
import { Segmented } from "./Segmented";

const PRODUCTS = [
  { value: "european", label: "European" },
  { value: "american", label: "American" },
  { value: "digital", label: "Digital" },
] as const satisfies readonly { value: ProductType; label: string }[];

const OPTION_TYPES = [
  { value: "call", label: "Call" },
  { value: "put", label: "Put" },
] as const;

const MODELS = [
  { value: "bsm", label: "Black–Scholes–Merton" },
  { value: "black76", label: "Black-76 (forward)" },
] as const;

const TREATMENTS = [
  { value: "escrowed", label: "Escrowed" },
  { value: "spot", label: "Spot jumps" },
] as const;

const CURRENCIES = ["EUR", "USD", "GBP", "CHF", "JPY"].map((c) => ({ value: c, label: c }));

/** Preferred method per product when the current one cannot price it. */
const PREFERRED: Record<ProductType, string> = { european: "analytic", american: "cn_pde", digital: "analytic" };

/** Keep the selected method valid for the product (e.g. switching to American leaves analytic). */
function useSupportedMethod(): { value: string; label: string }[] {
  const meta = useMeta();
  const product = useInputs((s) => s.inputs.productType);
  const method = useInputs((s) => s.inputs.method);
  const set = useInputs((s) => s.set);
  const options = (meta.data?.methods ?? [])
    .filter((m) => m.instruments.includes(product))
    .map((m) => ({ value: m.name, label: m.label }));
  const valid = options.some((o) => o.value === method);
  useEffect(() => {
    if (!meta.data || valid) return;
    const preferred = options.find((o) => o.value === PREFERRED[product]) ?? options[0];
    if (preferred) set("method", preferred.value);
  }, [meta.data, valid, options, product, set]);
  return options.length ? options : [{ value: method, label: method }];
}

export function InputsPanel() {
  const i = useInputs((s) => s.inputs);
  const set = useInputs((s) => s.set);
  const methods = useSupportedMethod();
  const black76 = i.model === "black76";
  const notUsed = "Not used under Black-76: the forward is quoted directly.";

  return (
    <div>
      <InputGroup id="product" title="Product">
        <div className="mb-1.5">
          <Segmented
            label="Product type"
            value={i.productType}
            options={PRODUCTS}
            onChange={(v) => {
              set("productType", v);
            }}
          />
        </div>
        <ControlRow label="Type">
          <Segmented
            label="Option type"
            value={i.optionType}
            options={OPTION_TYPES}
            onChange={(v) => {
              set("optionType", v);
            }}
          />
        </ControlRow>
        <NumericField
          id="strike"
          label="Strike"
          value={i.strike}
          onChange={(v) => {
            set("strike", v);
          }}
          step={1}
          dp={2}
          min={0.0001}
          help={{ title: "Strike K", definition: "Exercise price, in underlying price units." }}
        />
        <DateField
          id="expiry"
          label="Expiry"
          value={i.expiry}
          onChange={(v) => {
            set("expiry", v);
          }}
          help={{
            title: "Expiry T",
            definition:
              i.productType === "american"
                ? "Last exercise date. Exercise is allowed on any day up to expiry. τ = ACT/365F."
                : "Expiry and payment date. τ = ACT/365F from valuation date.",
          }}
        />
        {i.productType === "digital" && (
          <NumericField
            id="payout"
            label="Payout"
            value={i.payout}
            onChange={(v) => {
              set("payout", v);
            }}
            step={0.1}
            dp={2}
            min={0.0001}
            unit={i.currency}
            help={{
              title: "Digital payout Q",
              definition: "Cash paid per unit if the option expires in the money (cash-or-nothing).",
            }}
          />
        )}
        <NumericField
          id="quantity"
          label="Quantity"
          value={i.quantity}
          onChange={(v) => {
            set("quantity", v);
          }}
          step={1}
          dp={0}
          min={1}
          unit="units"
          help={{ title: "Quantity N", definition: "Units of underlying. Notional = N · S." }}
        />
        <SelectField
          id="currency"
          label="Currency"
          value={i.currency}
          options={CURRENCIES}
          onChange={(v) => {
            set("currency", v);
          }}
        />
      </InputGroup>

      <InputGroup id="market" title="Market">
        <DateField
          id="valuation-date"
          label="Valuation date"
          value={i.valuationDate}
          onChange={(v) => {
            set("valuationDate", v);
          }}
          help={{ title: "Valuation date", definition: "t = 0. Curves and vols are read from this date." }}
        />
        <NumericField
          id="spot"
          label={black76 ? "Forward" : "Spot"}
          value={i.spot}
          onChange={(v) => {
            set("spot", v);
          }}
          step={1}
          dp={2}
          min={0.0001}
          help={
            black76
              ? {
                  title: "Forward F",
                  definition: "Forward (futures) price for the option expiry. Black-76 underlying.",
                }
              : { title: "Spot S₀", definition: "Underlying price at the valuation date." }
          }
        />
        <RateField
          curve="rate"
          id="rate"
          label="Rate"
          help={{
            title: "Discount rate r",
            definition:
              "Zero rate, continuously compounded: flat, or a curve of tenor pillars with log-linear discount factors. Discounts cash flows and enters the forward.",
            formula: "P(0,T) = exp(−z(T)·T)",
          }}
        />
        <RateField
          curve="dividendYield"
          id="dividend-yield"
          label="Dividend yield"
          disabled={black76}
          help={{
            title: "Dividend yield q",
            definition: black76 ? notUsed : "Continuous dividend yield (flat or curve). Enters the forward only.",
          }}
        />
        <RateField
          curve="borrow"
          id="borrow"
          label="Repo / borrow"
          disabled={black76}
          help={{
            title: "Repo / borrow spread b",
            definition: black76
              ? notUsed
              : "Stock borrow cost over the discount rate (flat or curve). Enters the forward only, not discounting.",
            formula: "F = S₀ · P_q · P_b / P_r − dividends",
          }}
        />
        <NumericField
          id="vol"
          label="Volatility"
          value={i.volPct}
          onChange={(v) => {
            set("volPct", v);
          }}
          step={0.5}
          dp={2}
          min={0.01}
          max={500}
          unit="%"
          help={{ title: "Implied volatility σ", definition: "Flat Black implied volatility, annualised (ACT/365F)." }}
        />
      </InputGroup>

      <DividendsGroup disabled={black76} />

      <InputGroup id="model" title="Model & method">
        <SelectField
          wide
          id="model"
          label="Model"
          value={i.model}
          options={MODELS}
          onChange={(v) => {
            set("model", v);
          }}
        />
        {!black76 && (
          <SelectField
            wide
            id="dividend-treatment"
            label="Dividends"
            value={i.dividendTreatment}
            options={TREATMENTS}
            onChange={(v) => {
              set("dividendTreatment", v);
            }}
            help={{
              title: "Cash-dividend treatment",
              definition:
                "Escrowed: S − PV(cash dividends) is lognormal; Europeans are Black on the dividend-adjusted forward. Spot jumps: S is lognormal and drops by the dividend at each ex-date (PDE only).",
            }}
          />
        )}
        <SelectField
          wide
          id="method"
          label="Method"
          value={i.method}
          options={methods}
          onChange={(v) => {
            set("method", v);
          }}
        />
      </InputGroup>

      {i.productType === "european" && <ImpliedVolGroup />}
    </div>
  );
}
