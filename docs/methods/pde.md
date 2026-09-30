# Crank–Nicolson PDE

Code: `engine/methods/pde.py` (`cn_pde`).

**Supports:**
- European and American vanillas, and cash-or-nothing digitals.
- BSM under both dividend treatments, and Black-76.

## Equation and grid

In `x = ln X` (state `X`: escrowed-dividend spot, spot with jumps, or the Black-76 forward), solved
backward in time:

```
V_t + ½σ²·V_xx + (μ(t) − ½σ²)·V_x − r(t)·V = 0
```

**Rates:** `r(t)` and `μ(t)` are the local forward discount and carry rates over each step, taken
from the curves. Black-76 has `μ = 0`.

**Space grid:**
- Uniform in `x` with `ln K` exactly on a node.
- Half-width `n_std·σ√T`, default 5, extended if a requested spot falls outside.
- The grid does not depend on spot, so spot-bump greeks are smooth.

**Time grid:** `time_steps` uniform steps, with ex-dates inserted as extra nodes.

## Scheme

- **Crank–Nicolson.** The first `rannacher_steps` steps (default 2), and those after each dividend
  jump, are replaced by two implicit-Euler half steps each (Rannacher smoothing).
- **Tridiagonal solves:** LAPACK `dgtsv`.
- **Boundaries:** Dirichlet, from the forward asymptotes:
  - vanillas: `D(t,T)·max(ω(F_t(X) − K), 0)`, floored at intrinsic for Americans;
  - digitals: `D(t,T)·Q·1{ω(F_t − K) > 0}`.
- **Early exercise:** penalty method (Forsyth & Vetzal, *SIAM J. Sci. Comput.* 23, 2002).
  - Each step solves `(A + P)V = b + P·g` with `P = penalty·1{V < g}`.
  - The iteration is warm-started from the previous step's exercise region.
  - It stops when the region is stable or the update is below `penalty_tol`. That typically takes
    1–3 iterations.
- **Dividends:**
  - Escrowed: no jumps. Exercise uses `S = X/Π_t + E_t`, both cum and ex on ex-date nodes.
  - Spot jumps: `V(S, t⁻) = V(S(1−δ) − D, t⁺)` by cubic spline in `x`. A cash dividend larger than
    `S(1−δ)` is floored at the lowest node.
- **Digitals:** the payoff is cell-averaged (the node at the strike pays ½·Q), which keeps
  second-order convergence.
- **Output:** values at requested spots come from a cubic spline in `x`. The exercise boundary `S*(t)`
  is recorded per time node, as a gap where no interior node is exercised.

## Accuracy and cost (1Y ATM American put, σ = 25%, r = 5%, q = 2%)

| Grid (space × time) | Error vs converged | Price | + all greeks |
|---|---|---|---|
| 200 × 100 | 5.8e-3 | 20 ms | 0.2 s |
| 400 × 200 | 1.6e-3 | 31 ms | 0.4 s |
| **800 × 200 (default)** | **7.4e-4 (≈ 5e-5 relative)** | **44 ms** | **0.45 s** |
| 1600 × 400 | 2.4e-4 | 121 ms | 1.2 s |

The space error dominates. For Europeans and digitals the error falls 4× per doubling.

## Validation (`tests/unit/test_tree_pde.py`)

- **European and digital vs closed form (hypothesis):** within the observed refinement correction.
- **American vs QuantLib `FdBlackScholesVanillaEngine`:** Spot and Escrowed cash-dividend models,
  two resolutions on each side. Tolerance `|Δours| + |ΔQL| + 1e-5`.
- **American tree vs PDE** under escrowed dividends and term structures, and under Black-76: within
  2e-3.
- **Properties:**
  - American ≥ European ≥ intrinsic.
  - An American call with no carry equals the European to 1e-10.
  - The put boundary lies below K, rises to K at expiry, and vanishes just before a large cash
    dividend.

**Why the American tolerances need both corrections:** QuantLib's American FD converges only at
about first order. At 800×1600 it is 7e-4 below the common limit that the tree, our PDE and its own
finer grids agree on.

## Known limitations

- **Flat implied vol at the strike:** the local-vol PDE arrives in Phase 3.
- **Uniform grid:** a strike-concentrated grid would cut the space error. It is deferred until
  profiling shows the need.
- **Charts** (profiles, heatmaps) use the lighter scenario resolution (200 × 100 by default).
