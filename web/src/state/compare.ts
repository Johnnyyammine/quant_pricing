import { create } from "zustand";

import type { PriceRequest, PriceResponse } from "../api/types";
import type { Inputs } from "./inputs";

/** A pinned pricing state: inputs, the request they produce, and its result. */
export interface Pinned {
  inputs: Inputs;
  request: PriceRequest;
  result: PriceResponse;
  pinnedAt: number;
}

interface CompareStore {
  pinned: Pinned | null;
  pin: (p: Omit<Pinned, "pinnedAt">) => void;
  unpin: () => void;
}

export const useCompare = create<CompareStore>()((set) => ({
  pinned: null,
  pin: (p) => {
    set({ pinned: { ...p, pinnedAt: Date.now() } });
  },
  unpin: () => {
    set({ pinned: null });
  },
}));
