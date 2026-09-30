import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

import type { GreekKey } from "../api/types";
import type { GreekMode } from "../lib/greeks";

export type ThemePref = "system" | "light" | "dark";
export type AnalysisTab = "profiles" | "heatmap" | "diagnostics";
/** Analysis views, in tab order. Each view ships with the phase that makes it useful. */
export const TABS: { value: AnalysisTab; label: string }[] = [
  { value: "profiles", label: "Profiles" },
  { value: "heatmap", label: "Heatmap" },
  { value: "diagnostics", label: "Diagnostics" },
];

export type ProfileMetric = "value" | GreekKey;

export interface ProfileSettings {
  axis: "spot" | "time";
  metric: ProfileMetric;
  rangePct: number;
}

export interface HeatmapSettings {
  spotRangePct: number;
  volRangePts: number;
  steps: number;
  horizonDays: number;
  unit: "ccy" | "pct";
  vsPinned: boolean;
}

interface UiStore {
  theme: ThemePref;
  greekMode: GreekMode;
  tab: AnalysisTab;
  paletteOpen: boolean;
  collapsed: Record<string, boolean>;
  profile: ProfileSettings;
  heatmap: HeatmapSettings;
  setProfile: (p: Partial<ProfileSettings>) => void;
  setHeatmap: (h: Partial<HeatmapSettings>) => void;
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
      tab: "profiles",
      paletteOpen: false,
      collapsed: {},
      profile: { axis: "spot", metric: "value", rangePct: 30 },
      heatmap: { spotRangePct: 20, volRangePts: 10, steps: 21, horizonDays: 0, unit: "ccy", vsPinned: false },
      setProfile: (p) => {
        set((s) => ({ profile: { ...s.profile, ...p } }));
      },
      setHeatmap: (h) => {
        set((s) => ({ heatmap: { ...s.heatmap, ...h } }));
      },
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
      partialize: (s) => ({
        theme: s.theme,
        greekMode: s.greekMode,
        tab: s.tab,
        collapsed: s.collapsed,
        profile: s.profile,
        heatmap: { ...s.heatmap, vsPinned: false },
      }),
      merge: (persisted, current) => {
        // Tolerate preferences written by an older version (missing or renamed keys).
        const p = (persisted ?? {}) as Partial<UiStore>;
        const tabs: AnalysisTab[] = ["profiles", "heatmap", "diagnostics"];
        return {
          ...current,
          ...p,
          tab: p.tab && tabs.includes(p.tab) ? p.tab : current.tab,
          profile: { ...current.profile, ...p.profile },
          heatmap: { ...current.heatmap, ...p.heatmap },
        };
      },
    },
  ),
);
