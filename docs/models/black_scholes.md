# Black–Scholes–Merton and Black-76

Code: `engine/models/black_scholes.py`, `engine/models/black76.py`,
`engine/methods/black_formulas.py`.

## Dynamics

- **BSM:** `dS/S = (r − q − b) dt + σ dW` under the pricing measure. The market carries spot `S₀`,
  and the forward is `F = S₀·P_q·P_b/P_r`. See [`../conventions.md`](../conventions.md).
- **Black-76:** `dF/F = σ dW` for the forward (or future) to the option expiry. `MarketData.spot`
  holds the quoted `F`. The dividend and borrow curves are ignored, and the discount curve
  discounts the payoff.

In both models `σ` is read from the vol surface at the option's strike and expiry.

## Generalised (cost-of-carry) formula

Underlying `X`, carry `μ`, zero rates to expiry `T`:

```
F = X·e^{μT}    D = e^{−rT}    c = e^{(μ−r)T}    s = σ√T
d₁ = ln(F/K)/s + s/2    d₂ = d₁ − s    n₁ = φ(d₁)
V = D·ω·[F·Φ(ωd₁) − K·Φ(ωd₂)]
```

The two models are special cases:
- **BSM:** `X = S`, `μ = r − q − b`.
- **Black-76:** `X = F`, `μ = 0`.

## Greeks (pure model units)

| Greek | Formula |
|---|---|
| Δ = ∂V/∂X | `ω·c·Φ(ωd₁)` |
| Γ | `c·n₁ / (X·s)` |
| ν = ∂V/∂σ | `X·c·n₁·√T` |
| vanna | `−c·n₁·d₂/σ` |
| volga | `ν·d₁·d₂/σ` |
| Θ = ∂V/∂t | `−X·c·n₁·σ/(2√T) − ω(μ − r)·X·c·Φ(ωd₁) − ω·r·K·D·Φ(ωd₂)` |
| charm = ∂Δ/∂t | `−ω(μ − r)·c·Φ(ωd₁) − c·n₁·(2μT − d₂·s)/(2T·s)` |
| ρ = ∂V/∂r (BSM) | `ω·K·T·D·Φ(ωd₂)`: the forward moves with `r` |
| ρ (Black-76) | `−T·V`: the forward is held fixed |
| φ = ∂V/∂q (BSM) | `−ω·T·X·c·Φ(ωd₁)` |
| φ (Black-76) | `0` |

Θ and charm hold `r`, `μ` and `σ` fixed as `T` shrinks. The closed forms are used only for flat
curves and a flat surface; otherwise the bump layer computes them by rolling the valuation date.

## Numerics

The price is evaluated as `D·B(F, K, σ√T, ω)` with Jäckel's accurate normalised Black (see
[`../calibration/implied_vol.md`](../calibration/implied_vol.md)). In-the-money prices are
intrinsic plus the out-of-the-money counterpart, and out-of-the-money prices keep full *relative*
accuracy down to about 1e-290 (at that point floats become subnormal). This matters for implied
vols in the wings and for bucketed risk later on.

## Validation (`tests/unit/test_black_analytic.py`)

| Check | Tolerance |
|---|---|
| Haug (2nd ed.) 1.1.1–1.1.3 and 2.1.1–2.1.5; Hull worked example | quoted precision (4 dp / 2 dp) |
| QuantLib `AnalyticEuropeanEngine`, BSM and Black-76 (as GBS with q = r), hypothesis space: S ∈ [1, 1000], K/S ∈ [0.5, 2], T ∈ [1 d, 10 y], σ ∈ [2%, 150%], r ∈ [−2%, 12%], q ∈ [0, 8%], b ∈ [0, 3%] | price 1e-10 rel; Δ, Γ, ν, Θ, ρ, φ 1e-9 rel |
| Put–call parity `C − P = D(F − K)` | 1e-12·(F + K) |
| No-arbitrage bounds; monotone in σ and K; butterfly ≥ 0 on non-uniform strikes; monotone in total variance at fixed F | 1e-13·S |
| Every closed form vs Richardson-extrapolated bump-and-revalue (h, h/2; for time, 1 d and 2 d) | residual ≤ 5% of the removed h² term + 1e-6 rel + round-off ε·(V + S)/stencil |

The QuantLib comparison skips prices below 1e-8·S, where QuantLib's direct formula (not ours)
loses digits.

**Performance:** price plus all nine greeks takes about 20 µs (median). The target is 5 ms.

## Known limitations

- **Flat vol only.** The implied vol is flat per option (sticky strike under spot bumps). Smile
  dynamics arrive with vol surfaces in Phase 3.
- **Continuous carry only.** Discrete dividends arrive in Phase 2.
- **European exercise only.**
- **Expiry day.** At `T = 0` the price is intrinsic and Δ is a step (½ at the money); all other
  greeks are reported as 0.
