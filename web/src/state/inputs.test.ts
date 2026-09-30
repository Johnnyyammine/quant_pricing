import { describe, expect, it } from "vitest";

import { defaultInputs, toRequest, type Inputs } from "./inputs";

const base = defaultInputs(new Date(2026, 0, 2));

describe("toRequest", () => {
  it("converts display units to API decimals", () => {
    const req = toRequest(base);
    expect(req.market.rate).toBeCloseTo(0.03, 15);
    expect(req.market.vol).toBeCloseTo(0.2, 15);
    expect(req.settings.bumps?.spot_rel).toBeCloseTo(1e-3, 15);
    expect(req.settings.bumps?.rate_abs).toBeCloseTo(1e-4, 15);
    expect(req.settings.digital?.spread_width_rel).toBeCloseTo(0.01, 15);
    expect(req.market.valuation_date).toBe("2026-01-02");
    expect(req.instrument.expiry).toBe("2027-01-02");
    expect(req.instrument.type).toBe("european");
  });

  it("builds digital instruments with a payout", () => {
    const req = toRequest({ ...base, productType: "digital", payout: 5 });
    expect(req.instrument).toMatchObject({ type: "digital", payout: 5 });
  });

  it("resolves curve tenors against the valuation date and skips invalid ones", () => {
    const i: Inputs = {
      ...base,
      curves: {
        ...base.curves,
        rate: {
          mode: "curve",
          pillars: [
            { tenor: "6M", ratePct: 2 },
            { tenor: "oops", ratePct: 9 },
            { tenor: "2Y", ratePct: 3 },
          ],
        },
      },
    };
    expect(toRequest(i).market.rate).toEqual({
      pillars: [
        { date: "2026-07-02", rate: 0.02 },
        { date: "2028-01-02", rate: 0.03 },
      ],
    });
  });

  it("maps dividends and treatment", () => {
    const i: Inputs = {
      ...base,
      dividends: [{ id: 1, exDate: "2026-06-15", cash: 1.5, propPct: 1 }],
      dividendTreatment: "spot",
    };
    const req = toRequest(i);
    expect(req.market.dividends).toEqual([{ ex_date: "2026-06-15", cash: 1.5, proportional: 0.01 }]);
    expect(req.model.dividend_treatment).toBe("spot");
  });
});
