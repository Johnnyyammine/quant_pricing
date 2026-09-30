import { useCallback } from "react";

import { useCompare } from "../state/compare";
import { useInputs } from "../state/inputs";
import { usePrice } from "./usePrice";

/** Pin the current result for compare mode. Only a settled result (inputs = request) can be pinned. */
export function usePin() {
  const { data, request, pending, error } = usePrice();
  const inputs = useInputs((s) => s.inputs);
  const pinned = useCompare((s) => s.pinned);
  const pinState = useCompare((s) => s.pin);
  const unpin = useCompare((s) => s.unpin);
  const canPin = !!data && !pending && !error;
  const pin = useCallback(() => {
    if (data && canPin) pinState({ inputs, request, result: data.data });
  }, [data, canPin, pinState, inputs, request]);
  const toggle = useCallback(() => {
    if (pinned) unpin();
    else pin();
  }, [pinned, pin, unpin]);
  return { pinned, canPin, pin, unpin, toggle };
}
