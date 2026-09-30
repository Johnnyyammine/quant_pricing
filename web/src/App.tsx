import * as Tooltip from "@radix-ui/react-tooltip";

import { AnalysisTabs } from "./components/AnalysisTabs";
import { CommandPalette } from "./components/CommandPalette";
import { GreeksPanel } from "./components/GreeksPanel";
import { Headline } from "./components/Headline";
import { InputsPanel } from "./components/InputsPanel";
import { TopBar } from "./components/TopBar";
import { useApplyTheme } from "./hooks/useTheme";

export function App() {
  useApplyTheme();
  return (
    <Tooltip.Provider delayDuration={350} skipDelayDuration={150}>
      <div className="flex h-full flex-col">
        <TopBar />
        <div className="grid min-h-0 flex-1 grid-cols-1 lg:grid-cols-[296px_minmax(0,1fr)_340px]">
          <aside
            aria-label="Inputs"
            className="min-h-0 overflow-x-hidden overflow-y-auto border-r border-line bg-surface"
          >
            <InputsPanel />
          </aside>
          <main className="min-h-0 space-y-5 overflow-y-auto p-5">
            <Headline />
            <AnalysisTabs />
          </main>
          <aside className="min-h-0 overflow-y-auto border-l border-line bg-surface">
            <GreeksPanel />
          </aside>
        </div>
      </div>
      <CommandPalette />
    </Tooltip.Provider>
  );
}
