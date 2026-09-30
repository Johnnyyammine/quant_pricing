import { describe, expect, it } from "vitest";

import { addTenor, normaliseTenor } from "./dates";

describe("tenors", () => {
  it("normalises and validates", () => {
    expect(normaliseTenor(" 3m ")).toBe("3M");
    expect(normaliseTenor("10Y")).toBe("10Y");
    expect(normaliseTenor("0M")).toBeNull();
    expect(normaliseTenor("3X")).toBeNull();
  });
  it("adds calendar tenors", () => {
    expect(addTenor("2026-01-31", "1W")).toBe("2026-02-07");
    expect(addTenor("2026-01-15", "3M")).toBe("2026-04-15");
    expect(addTenor("2026-01-15", "2Y")).toBe("2028-01-15");
    expect(addTenor("2026-01-15", "bad")).toBeNull();
  });
});
