import type { GreekKey } from "../api/types";
import { usePrice } from "../hooks/usePrice";
import { formatNumber } from "../lib/format";
import { GREEKS, type GreekMode } from "../lib/greeks";
import { useUi } from "../state/ui";
import { Segmented } from "./Segmented";
import { Tip, TipBody } from "./Tip";

const MODES = [
  { value: "pure", label: "Pure" },
  { value: "cash", label: "Cash" },
] as const satisfies readonly { value: GreekMode; label: string }[];

const FIRST_ORDER: GreekKey[] = ["delta", "gamma", "vega", "theta", "rho", "phi"];

export function GreeksPanel() {
  const mode = useUi((s) => s.greekMode);
  const setMode = useUi((s) => s.setGreekMode);
  const { data, pending, error } = usePrice();
  const rows = data?.data.greeks[mode] ?? [];

  return (
    <section aria-label="Greeks" className="flex flex-col">
      <header className="flex items-center justify-between border-b border-line px-4 py-2.5">
        <h2 className="text-[11px] font-semibold uppercase tracking-[0.06em] text-fg-muted">Greeks</h2>
        <Segmented label="Greek units" size="sm" value={mode} options={MODES} onChange={setMode} />
      </header>
      <table className={`w-full transition-opacity ${pending || error ? "opacity-55" : ""}`}>
        <tbody>
          {rows.map((g) => {
            const meta = GREEKS[g.key];
            const secondOrderStart = !FIRST_ORDER.includes(g.key) && g.key === "vanna";
            return (
              <tr
                key={g.key}
                className={`group hover:bg-surface-hover ${secondOrderStart ? "border-t border-line" : ""}`}
                data-testid={`greek-${g.key}`}
              >
                <td className="py-[5px] pl-4 pr-2">
                  <Tip
                    content={
                      <TipBody
                        title={`${meta.label} (${meta.symbol})`}
                        definition={meta.definition}
                        formula={meta.formula}
                        unit={`${g.unit} · computed by ${g.source === "bump" ? "bump & revalue (central)" : "closed form"}`}
                      />
                    }
                  >
                    <span tabIndex={0} className="cursor-default text-[12.5px] text-fg outline-none">
                      {meta.label}
                    </span>
                  </Tip>
                </td>
                <td className="num py-[5px] pr-2 text-[12.5px]">{formatNumber(g.value, meta.dp[mode])}</td>
                <td className="w-[92px] whitespace-nowrap py-[5px] pr-4 text-[11px] text-fg-faint">{g.unit}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {!rows.length && <p className="px-4 py-3 text-[12px] text-fg-faint">{pending ? "Computing…" : "No greeks."}</p>}
    </section>
  );
}
