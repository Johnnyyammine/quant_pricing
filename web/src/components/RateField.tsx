import { normaliseTenor } from "../lib/dates";
import { useInputs, type CurveKey } from "../state/inputs";
import { FieldRow, NumberInput } from "./fields";

const FLAT_KEY = { rate: "ratePct", dividendYield: "dividendYieldPct", borrow: "borrowPct" } as const;

interface Help {
  title: string;
  definition: string;
  formula?: string;
}

/**
 * A continuously compounded rate input that is either flat or a pillar curve (tenor, zero rate).
 * Curves interpolate log-linearly in discount factors; tenors resolve against the valuation date.
 */
export function RateField({
  curve,
  id,
  label,
  help,
  disabled = false,
}: {
  curve: CurveKey;
  id: string;
  label: string;
  help: Help;
  disabled?: boolean;
}) {
  const inputs = useInputs((s) => s.inputs);
  const set = useInputs((s) => s.set);
  const setCurveMode = useInputs((s) => s.setCurveMode);
  const setPillar = useInputs((s) => s.setPillar);
  const addPillar = useInputs((s) => s.addPillar);
  const removePillar = useInputs((s) => s.removePillar);
  const c = inputs.curves[curve];
  const flatKey = FLAT_KEY[curve];
  const isCurve = c.mode === "curve";

  const toggle = (
    <button
      type="button"
      disabled={disabled}
      aria-pressed={isCurve}
      title={isCurve ? "Use a flat rate" : "Use a term structure (pillars)"}
      onClick={() => {
        setCurveMode(curve, isCurve ? "flat" : "curve");
      }}
      className={`h-7 shrink-0 rounded-md border px-1.5 text-[10.5px] disabled:opacity-40 ${
        isCurve ? "border-accent bg-accent-soft text-fg" : "border-line text-fg-faint hover:text-fg-muted"
      }`}
    >
      Curve
    </button>
  );

  return (
    <div>
      <FieldRow id={id} label={label} help={help} unit="%">
        <div className="flex gap-1">
          {isCurve ? (
            <div className="flex h-7 min-w-0 flex-1 items-center rounded-md border border-dashed border-line px-2 text-[11.5px] text-fg-muted">
              {c.pillars.length} pillars
            </div>
          ) : (
            <div className="min-w-0 flex-1">
              <NumberInput
                id={id}
                value={inputs[flatKey]}
                onChange={(v) => {
                  set(flatKey, v);
                }}
                step={0.05}
                dp={3}
                unit="%"
                disabled={disabled}
              />
            </div>
          )}
          {toggle}
        </div>
      </FieldRow>
      {isCurve && !disabled && (
        <div className="mb-1 ml-3 border-l border-line pl-3" aria-label={`${label} curve`}>
          {c.pillars.map((p, i) => {
            const valid = normaliseTenor(p.tenor) !== null;
            return (
              <div key={i} className="grid grid-cols-[56px_minmax(0,1fr)_20px] items-center gap-1.5 py-[2px]">
                <input
                  aria-label={`${label} pillar ${i + 1} tenor`}
                  aria-invalid={!valid}
                  value={p.tenor}
                  onChange={(e) => {
                    setPillar(curve, i, { tenor: e.target.value });
                  }}
                  onBlur={() => {
                    const t = normaliseTenor(p.tenor);
                    if (t) setPillar(curve, i, { tenor: t });
                  }}
                  className={`num h-7 rounded-md border bg-surface px-1.5 text-left text-[12px] outline-none focus:border-accent ${
                    valid ? "border-line" : "border-neg"
                  }`}
                />
                <NumberInput
                  ariaLabel={`${label} pillar ${i + 1} rate`}
                  value={p.ratePct}
                  onChange={(v) => {
                    setPillar(curve, i, { ratePct: v });
                  }}
                  step={0.05}
                  dp={3}
                  unit="%"
                />
                <button
                  type="button"
                  aria-label={`Remove ${label} pillar ${i + 1}`}
                  disabled={c.pillars.length <= 1}
                  onClick={() => {
                    removePillar(curve, i);
                  }}
                  className="text-[14px] leading-none text-fg-faint hover:text-neg disabled:opacity-30"
                >
                  ×
                </button>
              </div>
            );
          })}
          <button
            type="button"
            onClick={() => {
              addPillar(curve);
            }}
            className="mt-0.5 text-[11.5px] text-fg-muted hover:text-fg"
          >
            + Add pillar
          </button>
        </div>
      )}
    </div>
  );
}
