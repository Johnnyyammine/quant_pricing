# Leisen–Reimer tree

Code: `engine/methods/tree.py` (`lr_tree`).
Reference: D. Leisen & M. Reimer, "Binomial models for option valuation – examining and improving
convergence", *Applied Mathematical Finance* 3 (1996).

**Supports:**
- European and American vanillas.
- BSM with the escrowed dividend treatment, and Black-76.
- Not the spot-jump treatment with cash dividends: the tree would not recombine. It raises and
  points to the PDE.

## Construction

The tree is built on the driftless martingale part of the state (see
[`../models/curves_and_dividends.md`](../models/curves_and_dividends.md)):

```
X_t = X_0 · g(t) · M_t,   E[M_t] = 1,   node state X_0 · g(t_i) · u^j · d^(i−j)
```

- `g` is the deterministic carry growth.
- Each step discounts with `P(t_{i+1})/P(t_i)`.

So term-structure curves and escrowed dividends need no special handling. With `n` odd steps and
Peizer–Pratt method-2 inversion `h(z)`:

```
p = h(d₂),  p' = h(d₁),  u = p'/p,  d = (1 − p·u)/(1 − p)
```

where `d₁, d₂` are the Black d's on the forward `F = X_0·g(T)` and the strike. The tree is centred on
the strike, so its price is smooth in spot and the generic bump layer gives clean greeks.

American exercise compares continuation value with `max(ω(S − K), 0)` at each node:
- `S = a(t)·X + c(t)` maps the state back to spot.
- On an ex-date node, both the cum-dividend and ex-dividend spot are allowed.

Spots in a ladder are priced together: arrays of shape spots × nodes, one backward induction.

## Validation (`tests/unit/test_tree_pde.py`)

| Check | Tolerance |
|---|---|
| European vs QuantLib `BinomialVanillaEngine("lr")` (same lattice) | 1e-10 relative |
| European vs closed form, n and 2n + 1 steps (flat, term structures, escrowed dividends) | within the observed refinement correction |
| American vs QuantLib FD (two resolutions) | \|Δtree\| + \|ΔQL\| + 1e-5 |
| Ladder = per-spot evaluation | 1e-14 |

**QuantLib's American LR is not used as an oracle.** Its American prices can fall below its own
European LR prices. For example, S = K = 100, σ = 50%, r = 5%, q = 2%, 201 steps gives 19.605 for
the American vs 19.695 for the European, which is impossible for an American.

**Convergence:**
- **Europeans:** `O(n⁻²)`. The error falls 4× per doubling (1.7e-4 → 4.4e-5 → 1.1e-5 → 2.8e-6 →
  7.1e-7 at 51 … 801 steps).
- **Americans:** slower and oscillating, about `O(n⁻¹)`. At 401 steps a 1Y ATM put is about 1e-3
  from the converged value.

**Cost:** about 3.6 ms per price at 401 steps; about 0.2–0.3 s with all nine greeks.

## Known limitations

- **Early exercise around ex-dates** is resolved to one time step.
- **Spot-jump cash dividends** are not supported; use the PDE.
- **Flat implied vol at the strike:** local and stochastic vol arrive in Phases 3–4.
