# Conventions

These conventions apply across the engine, API and UI. A change here is a breaking change: update
the tests and the decision log in `CLAUDE.md` in the same PR.

## Time

- **Day count:** ACT/365 Fixed. `τ(d₁, d₂) = (d₂ − d₁).days / 365`. It is additive and
  antisymmetric.
- **Valuation granularity:** calendar dates only; there is no intraday time.
- **Calendar:** `WeekdayCalendar` treats Mon–Fri as business days and takes a pluggable holiday set.
  Adjustment is Following. Phase 0/1 products do not roll dates yet; schedules arrive in Phase 5.
- **Settlement:** Phase 0/1 options pay at expiry (no settlement lag).

## Rates and forwards

All pricing is forward-based. Curves are continuously compounded zero curves parametrised by year
fraction from the valuation date.

```
P_r(0,t)  discount curve          (discounting and forward)
P_q(0,t)  dividend-yield curve    (forward only)
P_b(0,t)  repo / borrow spread    (forward only; never used for discounting)

F(0,T) = S₀ · P_q(0,T) · P_b(0,T) / P_r(0,T)  =  S₀ · exp((r − q − b)·T)   for flat curves
```

- The borrow spread `b` is the stock-borrow cost *over* the discount rate. A long stock position
  financed at repo therefore earns `r − b − q`.
- Discrete cash and proportional dividends arrive in Phase 2 through `MarketData.forward(t)`. For
  the PDE they come with proper jump conditions `V(S, t_d⁻) = V(S − D, t_d⁺)`.

## Volatility

Black implied volatility `σ(K, T)`, annualised on ACT/365F. Vol bumps are **absolute**:
`0.01 = 1 vol point`. A vol bump shifts the whole surface in parallel. Bucketed vega arrives with
real surfaces (Phase 3).

## Greeks

The engine stores greeks in **pure model units**: partial derivatives of the unit price, with time
in years.

| Greek | Engine (pure model units) |
|---|---|
| Δ | ∂V/∂S |
| Γ | ∂²V/∂S² |
| ν | ∂V/∂σ |
| Θ | ∂V/∂t = −∂V/∂τ, per year, with spot, vols and rates held fixed |
| ρ | ∂V/∂r (discount curve; the forward moves with r) |
| φ | ∂V/∂q (dividend yield) |
| vanna | ∂²V/∂S∂σ |
| volga | ∂²V/∂σ² |
| charm | ∂Δ/∂t, per year |

`engine/risk/units.py` converts them to desk units. Take a position of `N` units at spot `S` in
currency `CCY`:

| Greek | Cash | Cash unit | Pure unit |
|---|---|---|---|
| Δ | Δ·S·N | CCY | % |
| Γ | Γ·S²·N/100 | CCY / 1% | %Δ / 1% |
| ν | ν·N/100 | CCY / vol pt | % / vol pt |
| Θ | Θ·N/365 | CCY / day | % / day |
| ρ | ρ·N/10⁴ | CCY / bp | % / bp |
| φ | φ·N/10⁴ | CCY / bp | % / bp |
| vanna | vanna·S·N/100 | CCY Δ / vol pt | %Δ / vol pt |
| volga | volga·N/10⁴ | CCY / vol pt² | % / vol pt² |
| charm | charm·S·N/365 | CCY Δ / day | %Δ / day |

**Pure = cash as a percentage of notional `N·S`**: `pure = 100 · cash / (N·S)`. So pure Δ is in %,
and pure Γ is the change in Δ (in %-points) for a 1% spot move, which equals `Γ·S`.

**Cash gamma** is the change in delta (in shares) for a 1% spot move, valued at spot:
`S · Γ · 0.01·S`. It does *not* include the `ΔS` term from revaluing the existing delta at the new
spot.

## Prices

- `PricingResult.price` is the **unit price**: per one unit of underlying, in the instrument
  currency.
- Position value = `N ×` unit price.
- **% of notional** = `100 · unit price / S₀`. Structured products (Phase 5) carry an explicit
  notional instead.

## Numerical settings

Every bump size, tolerance and grid size lives in `engine.settings.PricingSettings`. It is echoed in
every result and editable in the UI's Diagnostics tab. The bump defaults are:

| Setting | Default | Meaning |
|---|---|---|
| `bumps.spot_rel` | 1e-3 | h_S / S (0.1%) |
| `bumps.vol_abs` | 1e-3 | 0.1 vol point |
| `bumps.rate_abs` | 1e-4 | 1 bp, for ρ and φ |
| `bumps.time_days` | 1 | calendar-day roll, for Θ and charm |

See [`methods/bump_and_revalue.md`](methods/bump_and_revalue.md) for the stencils.
