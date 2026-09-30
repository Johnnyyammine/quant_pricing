import * as Tooltip from "@radix-ui/react-tooltip";
import type { ReactNode } from "react";

/** Hover/focus tooltip. Wrap a focusable or text element. */
export function Tip({
  content,
  children,
  side = "left",
}: {
  content: ReactNode;
  children: ReactNode;
  side?: "left" | "right" | "top" | "bottom";
}) {
  return (
    <Tooltip.Root>
      <Tooltip.Trigger asChild>{children}</Tooltip.Trigger>
      <Tooltip.Portal>
        <Tooltip.Content
          side={side}
          sideOffset={6}
          collisionPadding={8}
          className="z-50 max-w-72 rounded-md border border-line-strong bg-surface px-3 py-2 text-[12px] leading-snug text-fg shadow-lg"
        >
          {content}
        </Tooltip.Content>
      </Tooltip.Portal>
    </Tooltip.Root>
  );
}

/** Standard tooltip body: title, definition, formula, unit. */
export function TipBody({
  title,
  definition,
  formula,
  unit,
}: {
  title: string;
  definition: string;
  formula?: string;
  unit?: string;
}) {
  return (
    <div className="space-y-1">
      <div className="font-medium">{title}</div>
      <div className="text-fg-muted">{definition}</div>
      {formula && <div className="font-mono text-[11px] text-fg">{formula}</div>}
      {unit && <div className="text-fg-faint">Unit: {unit}</div>}
    </div>
  );
}
