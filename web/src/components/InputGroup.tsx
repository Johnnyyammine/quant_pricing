import * as Collapsible from "@radix-ui/react-collapsible";
import type { ReactNode } from "react";

import { useUi } from "../state/ui";
import { ChevronIcon } from "./icons";

export function InputGroup({ id, title, children }: { id: string; title: string; children: ReactNode }) {
  const collapsed = useUi((s) => s.collapsed[id] ?? false);
  const toggle = useUi((s) => s.toggleGroup);
  return (
    <Collapsible.Root
      open={!collapsed}
      onOpenChange={() => {
        toggle(id);
      }}
      className="border-b border-line"
    >
      <Collapsible.Trigger className="group flex w-full items-center justify-between px-4 py-2.5 text-left">
        <span className="text-[11px] font-semibold uppercase tracking-[0.06em] text-fg-muted group-hover:text-fg">
          {title}
        </span>
        <ChevronIcon className="text-fg-faint transition-transform group-data-[state=closed]:-rotate-90" />
      </Collapsible.Trigger>
      <Collapsible.Content className="px-4 pb-3">{children}</Collapsible.Content>
    </Collapsible.Root>
  );
}
