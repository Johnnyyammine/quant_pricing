import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useMemo } from "react";

import { getMeta, postPrice } from "../api/client";
import type { PriceRequest } from "../api/types";
import { toRequest, useInputs } from "../state/inputs";
import { useDebouncedValue } from "./useDebouncedValue";

/** Debounce before recomputing on input change, ms. */
export const RECOMPUTE_DEBOUNCE_MS = 120;

/** The current pricing request, debounced; `pending` is true while inputs are still settling. */
export function usePricingRequest(): { request: PriceRequest; settling: boolean } {
  const inputs = useInputs((s) => s.inputs);
  const live = useMemo(() => toRequest(inputs), [inputs]);
  const request = useDebouncedValue(live, RECOMPUTE_DEBOUNCE_MS);
  return { request, settling: live !== request };
}

/**
 * Live pricing: keyed on the debounced request so identical inputs hit the cache. Superseded
 * requests are aborted; the previous result stays on screen meanwhile.
 */
export function usePrice() {
  const { request, settling } = usePricingRequest();
  const query = useQuery({
    queryKey: ["price", request],
    queryFn: ({ signal }) => postPrice(request, signal),
    placeholderData: keepPreviousData,
    retry: false,
    staleTime: Infinity,
  });
  return { ...query, request, pending: settling || query.isFetching };
}

export function useMeta() {
  return useQuery({ queryKey: ["meta"], queryFn: ({ signal }) => getMeta(signal), staleTime: Infinity });
}
