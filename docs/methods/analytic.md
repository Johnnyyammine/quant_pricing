# Analytic method

`engine/methods/analytic.py`, registry name `analytic`.

**Supports:** `EuropeanOption` under `BlackScholesMerton` or `Black76`.

**Inputs:** zero rates to expiry are taken from the curves: `r = z_r(T)`, and for BSM
`μ = r − z_q(T) − z_b(T)`. `σ` is `vol(K, T)`. See [`../models/black_scholes.md`](../models/black_scholes.md)
for the formulas.

**Greeks:** all nine in closed form. There are two exceptions:
- **Non-flat market data:** Θ and charm are omitted when any curve is not flat or the vol surface
  is not flat; `engine.pricing.price` then fills them with bump-and-revalue (valuation-date roll).
- **Forced bumps:** `PricingSettings.force_bump_greeks = True` ignores the closed forms and bumps
  everything. The Diagnostics tab uses this to show analytic and bump greeks side by side.

**Diagnostics:** `σ`, `F`, `P(0,T)`, `τ`, `σ√T`, `d₁` and `d₂`.
