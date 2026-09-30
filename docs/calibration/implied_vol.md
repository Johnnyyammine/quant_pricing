# Implied volatility: Let's Be Rational

Code: `engine/calibration/implied_vol.py`, `engine/numerics/black.py`,
`engine/numerics/rational_cubic.py`.
Reference: P. Jäckel, "Let's Be Rational", *Wilmott* (2015), 75, 40–53.

## Method

Work in normalised coordinates: `x = ln(F/K)`, `s = σ√T`, `β = B/√(FK)` with `B` the undiscounted
price.

1. **Map to an OTM call.** In-the-money quotes are converted to out-of-the-money by subtracting the
   normalised intrinsic. Puts become calls through `b_put(x) = b_call(−x)`.
2. **Initial guess.** `(0, e^{x/2})` is split at `b_l < b_c < b_h` (with `s_c = √(2|x|)`). Each of
   the four segments gets a shape-preserving rational cubic guess (Delbourgo–Gregory):
   - the lowest and highest segments use transformed coordinates (lower map
     `f = 2π/√27·|x|·Φ(−|x|/(s√3))³`, upper map `f = Φ(−s/2)`);
   - the middle two segments use `s` directly.
3. **Refinement.** Two Householder(3) steps are taken on a segment-specific objective:
   - `1/ln b − 1/ln β` in the lowest segment;
   - `ln((b_max − β)/(b_max − b))` in the upper segment when `β > b_max/2`;
   - `b − β` otherwise.

   A bracket is maintained, and bisection takes over on oscillation or escape.
4. **Settings.** The iteration count is `PricingSettings.implied_vol.max_iterations` (default 2).

The normalised Black function uses four regions:
- asymptotic expansion for `h < −10`;
- 12th-order small-`t` expansion for `t < 0.21`;
- the direct formula when `h + t > 0.85`;
- the `erfcx` form otherwise.

Together they give full relative accuracy for out-of-the-money prices.

## Port notes

- **Control flow:** follows Jäckel's C++. The independent Python port `py_lets_be_rational`
  1.1.2, used here as an oracle, differs in two places: it resets the step inside the
  upper-segment loop, and it range-checks only one bound of `f''`. Neither changes results at
  test tolerances.
- **Licence:** Jäckel's licence notice is preserved in every ported file.

## Validation (`tests/unit/test_implied_vol.py`)

| Check | Tolerance |
|---|---|
| Normalised Black vs 50-digit mpmath, one case per region + ITM | 16 ε relative |
| Undiscounted Black vs mpmath, F ∈ [0.01, 100], K/F ∈ [0.05, 20], σ√T ∈ [1e-3, 3] | 1e-13 relative |
| Round trip `s → β → ŝ` over x ∈ [−8, 8], s ∈ [1e-3, 6], calls and puts | `|ŝ − s| ≤ 64 ε·s·cond`, with `cond = (β/β_otm)·(1 + β_otm/(s·∂b/∂s))` |
| σ recovery from dated prices (well-conditioned domain) | 1e-11 relative |
| Agreement with `py_lets_be_rational` | 1e-12 relative |
| Below intrinsic / at or above maximum | raise `BelowIntrinsicError` / `AboveMaximumError` |

**Stress run** on a dense grid (x ∈ [−30, 30], s ∈ [1e-4, 20], 7,192 points):
- worst error 7.3·ε·cond, with no failures;
- the reference port's worst is 6.7·ε·cond on the same grid.

## Known limitations

- **Subnormal prices.** Below about 1e-290 (normalised), prices lose mantissa bits and `s` can't be
  recovered to machine precision.
- **Uninformative prices.** Where the out-of-the-money part of an ITM price is below round-off
  relative to intrinsic, the price carries no information about `σ`. The solver returns a
  consistent answer, but nothing better is possible.
- **Flat vol only.** The API solves one flat vol per option. Surface calibration is Phase 3.
