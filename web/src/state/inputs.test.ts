import { describe, expect, it } from "vitest";

import { defaultInputs, toRequest } from "./inputs";

describe("toRequest", () => {
  it("converts display units to API decimals", () => {
    const req = toRequest(defaultInputs(new Date(2026, 0, 2)));
    expect(req.market.rate).toBeCloseTo(0.03, 15);
    expect(req.market.vol).toBeCloseTo(0.2, 15);
    expect(req.settings.bumps.spot_rel).toBeCloseTo(1e-3, 15);
    expect(req.settings.bumps.rate_abs).toBeCloseTo(1e-4, 15);
    expect(req.market.valuation_date).toBe("2026-01-02");
    expect(req.instrument.expiry).toBe("2027-01-02");
  });
});
