import { usePin } from "../hooks/usePin";
import { usePrice } from "../hooks/usePrice";
import { formatNumber } from "../lib/format";
import { COMPARED_FIELDS, useInputs } from "../state/inputs";

function Signed({ value, dp, unit }: { value: number; dp: number; unit: string }) {
  const tone = value > 0 ? "text-pos" : value < 0 ? "text-neg" : "text-fg-muted";
  return (
    <span className="flex items-baseline gap-1">
      <span className={`num ${tone}`}>{formatNumber(value, dp, { sign: true })}</span>
      <span className="text-[11px] text-fg-faint">{unit}</span>
    </span>
  );
}

/** Compare-mode strip: what changed since the pin, and the value difference. */
export function CompareBar() {
  const { pinned, unpin } = usePin();
  const inputs = useInputs((s) => s.inputs);
  const { data } = usePrice();
  if (!pinned) return null;
  const now = data?.data;
  const changed = COMPARED_FIELDS.filter((f) => f.format(pinned.inputs) !== f.format(inputs));
  const summary =
    changed.length === 0
      ? "No input changes yet: edit inputs to compare."
      : `Changed: ${changed.map((f) => `${f.label} ${f.format(pinned.inputs)} → ${f.format(inputs)}`).join(" · ")}`;
  const time = new Date(pinned.pinnedAt).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });

  return (
    <div
      className="flex flex-wrap items-center gap-x-6 gap-y-1 border-t border-line bg-accent-soft px-5 py-2 text-[12px]"
      data-testid="compare-bar"
    >
      <span className="font-medium text-fg">Pinned {time}</span>
      {now && (
        <>
          <span className="flex items-baseline gap-2 text-fg-muted">
            Δ value <Signed value={now.position_value - pinned.result.position_value} dp={2} unit={now.currency} />
          </span>
          <span className="flex items-baseline gap-2 text-fg-muted">
            Δ price <Signed value={now.pct_notional - pinned.result.pct_notional} dp={3} unit="% pts" />
          </span>
        </>
      )}
      <span className="flex-1" />
      <button
        type="button"
        onClick={unpin}
        className="rounded border border-line bg-surface px-2 py-0.5 text-[11.5px] text-fg-muted hover:border-line-strong hover:text-fg"
      >
        Unpin
      </button>
      <span className="basis-full text-[11.5px] leading-snug text-fg-muted">{summary}</span>
    </div>
  );
}
