import { PRODUCT_LABEL, useInputs } from "../state/inputs";
import { useUi, type ThemePref } from "../state/ui";
import { MOD_LABEL } from "../lib/platform";
import { LogoMark, SearchIcon } from "./icons";
import { Segmented } from "./Segmented";

const THEMES = [
  { value: "system", label: "Auto" },
  { value: "light", label: "Light" },
  { value: "dark", label: "Dark" },
] as const satisfies readonly { value: ThemePref; label: string }[];

export function TopBar() {
  const product = useInputs((s) => s.inputs.productType);
  const theme = useUi((s) => s.theme);
  const setTheme = useUi((s) => s.setTheme);
  const setPaletteOpen = useUi((s) => s.setPaletteOpen);
  return (
    <header className="flex h-11 items-center justify-between border-b border-line bg-surface px-4">
      <div className="flex items-center gap-2.5">
        <LogoMark />
        <span className="text-[13px] font-semibold tracking-tight">Quant Pricer</span>
        <span className="text-line-strong">/</span>
        <span className="text-[12.5px] text-fg-muted">{PRODUCT_LABEL[product]} option</span>
      </div>
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={() => {
            setPaletteOpen(true);
          }}
          className="flex h-7 w-60 items-center gap-2 rounded-md border border-line bg-surface-2 px-2.5 text-[12px] text-fg-faint hover:border-line-strong hover:text-fg-muted"
        >
          <SearchIcon />
          <span className="flex-1 text-left">Commands</span>
          <kbd className="rounded border border-line bg-surface px-1.5 font-sans text-[10.5px] text-fg-muted">
            {MOD_LABEL}
          </kbd>
        </button>
        <Segmented label="Theme" size="sm" value={theme} options={THEMES} onChange={setTheme} />
      </div>
    </header>
  );
}
