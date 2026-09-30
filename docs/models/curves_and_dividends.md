# Curves, discrete dividends and the forward

Code: `engine/market/curves.py`, `engine/market/dividends.py`, `engine/market/market_data.py`,
`engine/methods/dynamics.py`.

## Zero curves

`ZeroCurve` holds pillar zero rates (continuously compounded, ACT/365F).
- **Interpolation:** `ln P(0,t)` is interpolated linearly between `(0, 0)` and `(t_i, −z_i t_i)`, so
  instantaneous forwards are piecewise flat.
- **Extrapolation:** flat zero rate before the first pillar; the last forward is extended beyond the
  last pillar.
- **Shifts:** a parallel shift of the pillars shifts `z(t)` by exactly `dz` for every `t`. ρ and φ
  are sensitivities to this shift.
- **Validation:** against QuantLib `DiscountCurve`, which is log-linear.

**Rolling the valuation date** (for Θ, charm, and time profiles) realises forwards:
`P'(0,t) = P(0,t+h)/P(0,h)`. The market is unchanged by calendar date, which makes theta the carry
theta. Flat curves are invariant. A backward roll is well defined, since negative `t` uses the first
segment.

## Discrete dividends

- **Ex-date convention:** at the open of the ex-date, `S → S·(1 − δ) − D`, proportional part first.
- **Payment:** on the ex-date (no payment lag).
- **Which dividends count:** a dividend is future when its ex-date is after the valuation date. It
  affects an option expiring on its ex-date.

**Forward.** With growth `G(t) = P_q(t)·P_b(t)/P_r(t)`:

```
F(0,T) = S·A(T) − Σ D_i·B_i(T),   A = G(T)·Π_{t_j≤T}(1−δ_j),   B_i = G(T)/G(t_i)·Π_{t_i<t_j≤T}(1−δ_j)
∂F/∂S = A,   ∂F/∂r = T·S·A − Σ D_i·(T − t_i)·B_i,   ∂F/∂q = ∂F/∂b = −∂F/∂r
```

The forward is checked against an independent forward recursion, and its sensitivities against
finite differences.

**Escrowed decomposition.** `S_t = Y_t/Π_t + E_t`, where:
- `Y` is a continuous lognormal with `Y_T = S_T`;
- `Π_t = Π_{t<t_j≤T}(1−δ_j)`;
- `E_t = Σ_{t<t_i≤T} D_i·G(t)/G(t_i)/Π_{t<t_j≤t_i}(1−δ_j)`.

It is verified via `F = (S − E_t)·Π_t·G(T)/G(t)` after rolling. Cum-dividend variants include an
ex-date at `t` itself, for exercise decisions.

## Dividend treatments (BSM)

| Treatment | Dynamics | Europeans | Americans |
|---|---|---|---|
| Escrowed (default) | `Y = (S − E)·Π` lognormal with vol σ | Exactly Black on the dividend-adjusted forward (closed form) | Tree or PDE (same model: side by side compares numerics only) |
| Spot jumps | `S` lognormal with vol σ between ex-dates; jumps at ex-dates | PDE only | PDE only |

With proportional dividends only, the two coincide. The escrowed model is the one consistent with
implied vols quoted against forwards. Under spot jumps, the same σ gives slightly different European
prices; that is a model difference, not a numerical one.

**QuantLib as oracle:** QuantLib's escrowed engines discount dividends at `r` only (not `r − q − b`).
Oracle comparisons therefore use `q = b = 0`, where both agree. The general forward is checked
independently.

## Known limitations

- **Deterministic rates and dividends.** Dividend yield curves and cash dividends are market inputs,
  not stochastic.
- **Escrowed state must stay positive:** a spot below the PV of the escrowed dividends is rejected.
