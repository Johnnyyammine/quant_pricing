import { useInputs } from "../state/inputs";
import { NumberInput } from "./fields";
import { InputGroup } from "./InputGroup";
import { Tip, TipBody } from "./Tip";

/** Discrete dividends: ex-date, cash per share and proportional part. */
export function DividendsGroup({ disabled }: { disabled: boolean }) {
  const dividends = useInputs((s) => s.inputs.dividends);
  const add = useInputs((s) => s.addDividend);
  const update = useInputs((s) => s.updateDividend);
  const remove = useInputs((s) => s.removeDividend);

  return (
    <InputGroup id="dividends" title={`Dividends${dividends.length ? ` · ${dividends.length}` : ""}`}>
      {disabled && dividends.length > 0 && (
        <p className="mb-1.5 text-[11.5px] text-fg-faint">Ignored under Black-76 (in the quoted forward).</p>
      )}
      {dividends.length > 0 && (
        <div
          className={`grid grid-cols-[minmax(0,1fr)_54px_50px_12px] gap-x-1.5 gap-y-1 ${disabled ? "opacity-45" : ""}`}
        >
          <Tip
            side="right"
            content={
              <TipBody
                title="Discrete dividends"
                definition="At the open of the ex-date S → S·(1 − prop) − cash. Paid on the ex-date. Ex-dates on or before the valuation date are ignored; an ex-date on expiry counts."
              />
            }
          >
            <span tabIndex={0} className="text-[11px] text-fg-faint">
              Ex-date
            </span>
          </Tip>
          <span className="text-right text-[11px] text-fg-faint">Cash</span>
          <span className="text-right text-[11px] text-fg-faint">Prop. %</span>
          <span />
          {dividends.map((d, i) => (
            <div key={d.id} className="contents">
              <input
                type="date"
                aria-label={`Dividend ${i + 1} ex-date`}
                value={d.exDate}
                disabled={disabled}
                onChange={(e) => {
                  if (e.target.value) update(d.id, { exDate: e.target.value });
                }}
                className="num h-7 min-w-0 rounded-md border border-line bg-surface px-1.5 text-[11.5px] outline-none focus:border-accent"
              />
              <NumberInput
                ariaLabel={`Dividend ${i + 1} cash`}
                value={d.cash}
                onChange={(v) => {
                  update(d.id, { cash: v });
                }}
                step={0.1}
                dp={2}
                min={0}
                disabled={disabled}
              />
              <NumberInput
                ariaLabel={`Dividend ${i + 1} proportional`}
                value={d.propPct}
                onChange={(v) => {
                  update(d.id, { propPct: v });
                }}
                step={0.1}
                dp={2}
                min={0}
                max={99}
                disabled={disabled}
              />
              <button
                type="button"
                aria-label={`Remove dividend ${i + 1}`}
                onClick={() => {
                  remove(d.id);
                }}
                className="text-[14px] leading-none text-fg-faint hover:text-neg"
              >
                ×
              </button>
            </div>
          ))}
        </div>
      )}
      <button type="button" onClick={add} className="mt-1.5 text-[11.5px] text-fg-muted hover:text-fg">
        + Add dividend
      </button>
    </InputGroup>
  );
}
