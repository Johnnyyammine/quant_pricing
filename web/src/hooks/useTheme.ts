import { useEffect } from "react";

import { useUi } from "../state/ui";

/** Apply the theme preference to <html data-theme>, following the OS when set to "system". */
export function useApplyTheme(): void {
  const theme = useUi((s) => s.theme);
  useEffect(() => {
    const mq = matchMedia("(prefers-color-scheme: dark)");
    const apply = () => {
      const dark = theme === "dark" || (theme === "system" && mq.matches);
      document.documentElement.dataset.theme = dark ? "dark" : "light";
    };
    apply();
    mq.addEventListener("change", apply);
    return () => {
      mq.removeEventListener("change", apply);
    };
  }, [theme]);
}
