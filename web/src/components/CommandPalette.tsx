import { Command } from "cmdk";
import { useEffect } from "react";

import { useInputs } from "../state/inputs";
import { useUi } from "../state/ui";

interface Action {
  id: string;
  group: string;
  label: string;
  run: () => void;
}

function focusField(id: string) {
  // Wait for the dialog to close and return focus before moving it.
  requestAnimationFrame(() => {
    const el = document.getElementById(id);
    if (el instanceof HTMLInputElement) {
      el.focus();
      el.select();
    }
  });
}

export function CommandPalette() {
  const open = useUi((s) => s.paletteOpen);
  const setOpen = useUi((s) => s.setPaletteOpen);
  const ui = useUi();
  const set = useInputs((s) => s.set);
  const reset = useInputs((s) => s.reset);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen(!useUi.getState().paletteOpen);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
    };
  }, [setOpen]);

  const actions: Action[] = [
    {
      id: "call",
      group: "Product",
      label: "European call",
      run: () => {
        set("optionType", "call");
      },
    },
    {
      id: "put",
      group: "Product",
      label: "European put",
      run: () => {
        set("optionType", "put");
      },
    },
    {
      id: "diag",
      group: "Go to",
      label: "Diagnostics",
      run: () => {
        ui.setTab("diagnostics");
      },
    },
    {
      id: "f-spot",
      group: "Go to",
      label: "Spot input",
      run: () => {
        focusField("spot");
      },
    },
    {
      id: "f-strike",
      group: "Go to",
      label: "Strike input",
      run: () => {
        focusField("strike");
      },
    },
    {
      id: "f-vol",
      group: "Go to",
      label: "Volatility input",
      run: () => {
        focusField("vol");
      },
    },
    {
      id: "pure",
      group: "Greeks",
      label: "Show pure greeks (% of notional)",
      run: () => {
        ui.setGreekMode("pure");
      },
    },
    {
      id: "cash",
      group: "Greeks",
      label: "Show cash greeks",
      run: () => {
        ui.setGreekMode("cash");
      },
    },
    {
      id: "t-sys",
      group: "Theme",
      label: "Theme: follow system",
      run: () => {
        ui.setTheme("system");
      },
    },
    {
      id: "t-light",
      group: "Theme",
      label: "Theme: light",
      run: () => {
        ui.setTheme("light");
      },
    },
    {
      id: "t-dark",
      group: "Theme",
      label: "Theme: dark",
      run: () => {
        ui.setTheme("dark");
      },
    },
    { id: "reset", group: "Inputs", label: "Reset all inputs to defaults", run: reset },
  ];
  const groups = [...new Set(actions.map((a) => a.group))];

  return (
    <Command.Dialog
      open={open}
      onOpenChange={setOpen}
      label="Command palette"
      overlayClassName="fixed inset-0 z-40 bg-black/25 dark:bg-black/50"
      contentClassName="fixed left-1/2 top-[18vh] z-50 w-[560px] max-w-[calc(100vw-32px)] -translate-x-1/2 overflow-hidden rounded-xl border border-line-strong bg-surface shadow-2xl"
    >
      <Command.Input
        placeholder="Type a command…"
        className="w-full border-b border-line bg-transparent px-4 py-3 text-[14px] text-fg outline-none placeholder:text-fg-faint"
      />
      <Command.List className="max-h-[360px] overflow-y-auto p-1.5">
        <Command.Empty className="px-3 py-6 text-center text-[12px] text-fg-faint">No matching command.</Command.Empty>
        {groups.map((g) => (
          <Command.Group
            key={g}
            heading={g}
            className="[&_[cmdk-group-heading]]:px-2.5 [&_[cmdk-group-heading]]:pb-1 [&_[cmdk-group-heading]]:pt-2 [&_[cmdk-group-heading]]:text-[11px] [&_[cmdk-group-heading]]:font-medium [&_[cmdk-group-heading]]:text-fg-faint"
          >
            {actions
              .filter((a) => a.group === g)
              .map((a) => (
                <Command.Item
                  key={a.id}
                  value={`${a.group} ${a.label}`}
                  onSelect={() => {
                    setOpen(false);
                    a.run();
                  }}
                  className="cursor-default rounded-md px-2.5 py-1.5 text-[13px] text-fg data-[selected=true]:bg-accent-soft"
                >
                  {a.label}
                </Command.Item>
              ))}
          </Command.Group>
        ))}
      </Command.List>
    </Command.Dialog>
  );
}
