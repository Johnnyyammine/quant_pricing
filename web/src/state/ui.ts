import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

import type { GreekMode } from "../lib/greeks";

export type ThemePref = "system" | "light" | "dark";
export type AnalysisTab = "diagnostics";

interface UiStore {
  theme: ThemePref;
  greekMode: GreekMode;
  tab: AnalysisTab;
  paletteOpen: boolean;
  collapsed: Record<string, boolean>;
  setTheme: (t: ThemePref) => void;
  setGreekMode: (m: GreekMode) => void;
  setTab: (t: AnalysisTab) => void;
  setPaletteOpen: (open: boolean) => void;
  toggleGroup: (id: string) => void;
}

/** localStorage can throw (private mode, blocked storage); fall back to in-memory. */
const safeStorage = createJSONStorage(() => {
  try {
    localStorage.setItem("qp-probe", "1");
    localStorage.removeItem("qp-probe");
    return localStorage;
  } catch {
    const mem = new Map<string, string>();
    return {
      getItem: (k: string) => mem.get(k) ?? null,
      setItem: (k: string, v: string) => void mem.set(k, v),
      removeItem: (k: string) => void mem.delete(k),
    };
  }
});

export const useUi = create<UiStore>()(
  persist(
    (set) => ({
      theme: "system",
      greekMode: "cash",
      tab: "diagnostics",
      paletteOpen: false,
      collapsed: {},
      setTheme: (theme) => {
        set({ theme });
      },
      setGreekMode: (greekMode) => {
        set({ greekMode });
      },
      setTab: (tab) => {
        set({ tab });
      },
      setPaletteOpen: (paletteOpen) => {
        set({ paletteOpen });
      },
      toggleGroup: (id) => {
        set((s) => ({ collapsed: { ...s.collapsed, [id]: !s.collapsed[id] } }));
      },
    }),
    {
      name: "qp-ui",
      storage: safeStorage,
      partialize: (s) => ({ theme: s.theme, greekMode: s.greekMode, tab: s.tab, collapsed: s.collapsed }),
    },
  ),
);
