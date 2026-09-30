export const IS_MAC = typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.userAgent);
export const MOD_LABEL = IS_MAC ? "⌘K" : "Ctrl K";
