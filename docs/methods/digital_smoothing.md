# Digital greek smoothing

Code: `engine/risk/smoothing.py`.
Setting: `PricingSettings.digital.spread_width_rel` (default 1% of strike).

A cash-or-nothing digital's Δ and Γ blow up near expiry at the strike. Its greeks are therefore taken
from a centred spread of width `w = ρ·K`:

```
call:  Q/w · [C(K − w/2) − C(K + w/2)]        put:  Q/w · [P(K + w/2) − P(K − w/2)]
```

- **Replica greeks:** priced with the same method and model, so they are analytic under the analytic
  method and bumped under the PDE.
- **Price:** always exact (closed form or cell-averaged PDE).
- **Diagnostics:** report the replica value and the smoothing bias (replica − exact).
- **Exact greeks:** `ρ = 0` gives the exact closed-form digital greeks. These are validated against
  QuantLib and Richardson bumps.
- **Convergence:** as `ρ → 0`, the replica greeks converge to the exact ones (tested).

With a vol smile (Phase 3), each leg reads its own implied vol. The replica then carries the skew term
of digital risk, `−∂C/∂K` including `∂σ/∂K`, which is the main reason desks book digitals this way.

**Generality:** the proxy mechanism is generic. Any instrument can declare a smoothed replica for its
greeks without the pricing entry point special-casing it.
