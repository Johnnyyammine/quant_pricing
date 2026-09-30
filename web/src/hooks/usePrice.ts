import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useMemo } from "react";

import { getMeta, postPrice } from "../api/client";
import { toRequest, useInputs } from "../state/inputs";
import { useDebouncedValue } from "./useDebouncedValue";

/** Debounce before recomputing on input change, ms. */
export const RECOMPUTE_DEBOUNCE_MS = 120;

/**
 * Live pricing: the request is derived from inputs, debounced, and keyed so identical inputs hit
 * the cache. Superseded requests are aborted; the previous result stays on screen meanwhile.
 */
export function usePrice() {
  const inputs = useInputs((s) => s.inputs);
  const request = useMemo(() => toRequest(inputs), [inputs]);
  const debounced = useDebouncedValue(request, RECOMPUTE_DEBOUNCE_MS);
  const query = useQuery({
    queryKey: ["price", debounced],
    queryFn: ({ signal }) => postPrice(debounced, signal),
    placeholderData: keepPreviousData,
    retry: false,
    staleTime: Infinity,
  });
  const pending = request !== debounced || query.isFetching;
  return { ...query, pending };
}

export function useMeta() {
  return useQuery({ queryKey: ["meta"], queryFn: ({ signal }) => getMeta(signal), staleTime: Infinity });
}
