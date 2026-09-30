import * as Tabs from "@radix-ui/react-tabs";

import { useUi, type AnalysisTab } from "../state/ui";
import { Diagnostics } from "./Diagnostics";

/** Analysis views. Each view ships with the phase that makes it useful (Profiles, Heatmap: Phase 1). */
const TABS: { value: AnalysisTab; label: string }[] = [{ value: "diagnostics", label: "Diagnostics" }];

export function AnalysisTabs() {
  const tab = useUi((s) => s.tab);
  const setTab = useUi((s) => s.setTab);
  return (
    <Tabs.Root
      value={tab}
      onValueChange={(v) => {
        setTab(v as AnalysisTab);
      }}
    >
      <Tabs.List aria-label="Analysis views" className="mb-4 flex gap-5 border-b border-line">
        {TABS.map((t) => (
          <Tabs.Trigger
            key={t.value}
            value={t.value}
            className="-mb-px border-b-2 border-transparent pb-2 text-[12.5px] font-medium text-fg-muted hover:text-fg data-[state=active]:border-accent data-[state=active]:text-fg"
          >
            {t.label}
          </Tabs.Trigger>
        ))}
      </Tabs.List>
      <Tabs.Content value="diagnostics" className="outline-none">
        <Diagnostics />
      </Tabs.Content>
    </Tabs.Root>
  );
}
