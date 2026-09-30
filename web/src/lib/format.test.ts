import { describe, expect, it } from "vitest";

import { formatNumber, parseNumber, roundTo } from "./format";

describe("formatNumber", () => {
  it("uses fixed decimals and grouping", () => {
    expect(formatNumber(1234.5, 2)).toBe("1,234.50");
    expect(formatNumber(1234.5, 2, { group: false })).toBe("1234.50");
  });
  it("uses a true minus sign", () => {
    expect(formatNumber(-0.125, 3)).toBe("−0.125");
  });
  it("never prints negative zero", () => {
    expect(formatNumber(-0.0001, 2)).toBe("0.00");
    expect(formatNumber(-0, 2)).toBe("0.00");
  });
  it("optionally signs positives", () => {
    expect(formatNumber(1.5, 1, { sign: true })).toBe("+1.5");
    expect(formatNumber(0, 1, { sign: true })).toBe("0.0");
  });
  it("renders non-finite as a dash", () => {
    expect(formatNumber(Number.NaN, 2)).toBe("—");
  });
});

describe("parseNumber", () => {
  it("accepts minus variants and separators", () => {
    expect(parseNumber(" −1,250.5 ")).toBe(-1250.5);
    expect(parseNumber("-3")).toBe(-3);
  });
  it("rejects partial input", () => {
    expect(parseNumber("")).toBeNull();
    expect(parseNumber("-")).toBeNull();
    expect(parseNumber("1e")).toBeNull();
  });
});

describe("roundTo", () => {
  it("removes floating noise", () => {
    expect(roundTo(0.1 + 0.2, 4)).toBe(0.3);
  });
});
