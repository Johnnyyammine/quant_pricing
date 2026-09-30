# Bump-and-revalue greeks

`engine/risk/greeks.py` computes any greek that a method does not supply in closed form. It works
for every instrument, because each greek is defined as a derivative along a market transformation
(`engine/risk/bumps.py`), never as a property of a product.

## Stencils (central, O(h²))

Notation:
- `h_S = spot_rel · S`
- `h_σ = vol_abs`
- `h_r = rate_abs`
- `h_t = time_days / 365`
- `V(±S)` means spot multiplied by `1 ± spot_rel`

```
Δ      = [V(+S) − V(−S)] / 2h_S
Γ      = [V(+S) − 2V + V(−S)] / h_S²
ν      = [V(+σ) − V(−σ)] / 2h_σ
volga  = [V(+σ) − 2V + V(−σ)] / h_σ²
vanna  = [V(+S+σ) − V(+S−σ) − V(−S+σ) + V(−S−σ)] / 4 h_S h_σ
ρ      = [V(+r) − V(−r)] / 2h_r
φ      = [V(+q) − V(−q)] / 2h_r
Θ      = [V(t+h_t) − V(t−h_t)] / 2h_t
charm  = [Δ(t+h_t) − Δ(t−h_t)] / 2h_t
```

- **Time rolls** move the valuation date and hold spot, vols and rates fixed.
- **Near maturity:** if the instrument matures within `h_t`, Θ and charm switch to a backward
  one-sided difference (O(h)) so no roll steps past maturity, and a warning is attached to the
  result.
- **Spot ladders:** stencil points are grouped by their non-spot bump (vol, rate, yield, time). Each
  group is one call to `PricingMethod.evaluate_ladder(market, spot multipliers)`:
  - All nine greeks need 19 stencil points, but only nine market revaluations.
  - A PDE shares one solve across all spots in a group, and the tree vectorises them.
  - Profiles evaluate every spot of every stencil in the same nine calls.

## Choosing bump sizes

The truncation error is `O(h²)` and the rounding error is `O(ε·V/h)`, or `O(ε·V/h²)` for second
derivatives.
- **Smooth analytic prices:** the defaults (0.1% spot, 0.1 vol pt, 1 bp, 1 day) balance the two at
  roughly 1e-6 relative accuracy.
- **Monte Carlo (Phase 4):** use larger bumps together with common random numbers.
- **Digital-like payoffs:** where bumping is noisy, use pathwise or likelihood-ratio estimators.

## Validation

`tests/unit/test_bump_greeks.py` checks every stencil against a quadratic price function. Central
differences are exact for quadratics, so the only error left is rounding. The test also checks the
revaluation count and the one-sided fallback at maturity.

## Known limitations

- **Vol bumps are parallel only.** Bucketed vega arrives with vol surfaces (Phase 3).
- **Rate bumps are parallel only.** Curve buckets arrive with term structures (Phase 2).
- **No bump guard at low vol.** A vol bump larger than the current vol raises a `MarketDataError`
  from the surface; a safe bump is not substituted.
