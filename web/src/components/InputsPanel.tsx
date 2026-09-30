import { useMeta } from "../hooks/usePrice";
import { useInputs } from "../state/inputs";
import { DateField, NumericField, SelectField, ControlRow } from "./fields";
import { InputGroup } from "./InputGroup";
import { Segmented } from "./Segmented";

const OPTION_TYPES = [
  { value: "call", label: "Call" },
  { value: "put", label: "Put" },
] as const;

const CURRENCIES = ["EUR", "USD", "GBP", "CHF", "JPY"].map((c) => ({ value: c, label: c }));

export function InputsPanel() {
  const i = useInputs((s) => s.inputs);
  const set = useInputs((s) => s.set);
  const meta = useMeta();
  const methods = meta.data?.methods.map((m) => ({ value: m.name, label: m.label })) ?? [
    { value: i.method, label: i.method },
  ];

  return (
    <div>
      <InputGroup id="product" title="Product">
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
          help={{ title: "Expiry T", definition: "Expiry and payment date. τ = ACT/365F from valuation date." }}
        />
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
          label="Spot"
          value={i.spot}
          onChange={(v) => {
            set("spot", v);
          }}
          step={1}
          dp={2}
          min={0.0001}
          help={{ title: "Spot S₀", definition: "Underlying price at the valuation date." }}
        />
        <NumericField
          id="rate"
          label="Rate"
          value={i.ratePct}
          onChange={(v) => {
            set("ratePct", v);
          }}
          step={0.05}
          dp={3}
          unit="%"
          help={{
            title: "Discount rate r",
            definition: "Flat zero rate, continuously compounded. Discounts cash flows and enters the forward.",
            formula: "P(0,T) = exp(−rT)",
          }}
        />
        <NumericField
          id="dividend-yield"
          label="Dividend yield"
          value={i.dividendYieldPct}
          onChange={(v) => {
            set("dividendYieldPct", v);
          }}
          step={0.05}
          dp={3}
          unit="%"
          help={{ title: "Dividend yield q", definition: "Continuous dividend yield. Enters the forward only." }}
        />
        <NumericField
          id="borrow"
          label="Repo / borrow"
          value={i.borrowPct}
          onChange={(v) => {
            set("borrowPct", v);
          }}
          step={0.05}
          dp={3}
          unit="%"
          help={{
            title: "Repo / borrow spread b",
            definition: "Stock borrow cost over the discount rate. Enters the forward only, not discounting.",
            formula: "F = S₀ · exp((r − q − b)T)",
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

      <InputGroup id="model" title="Model & method">
        <SelectField
          wide
          id="model"
          label="Model"
          value="bsm"
          options={[{ value: "bsm", label: "Black–Scholes–Merton" }]}
          onChange={() => undefined}
          disabled
        />
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
    </div>
  );
}
