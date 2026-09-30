# CLAUDE.md

Quant Pricer is a local pricing and risk workstation for equity derivatives and structured products.
The user is a senior quant (structured products, countervaluation, model validation). Don't simplify
the finance; be rigorous about numerics, conventions and tests.

**Guiding principle: depth over breadth.** Every feature earns its place. Pick one correct,
well-tested way of doing each thing.

## Architecture

```
engine/          Pure Python pricing library (numpy/scipy only). No web, API or UI imports.
  dates.py         ACT/365F, weekday calendar
  settings.py      PricingSettings: every bump / tolerance / grid size lives here
  results.py       Greek, Greeks, Diagnostics, PricingResult
  pricing.py       price(instrument, market, model, method, settings), the single entry point
  errors.py        PricingError hierarchy
  numerics/        normal.py (Φ, erfcx, Φ⁻¹), black.py (Jäckel accurate normalised Black),
                   rational_cubic.py (Delbourgo–Gregory)
  market/          RateCurve, VolSurface protocols + flat impls; MarketData (forward, df)
  instruments/     Pure data (frozen dataclasses). No pricing logic.
  models/          BlackScholesMerton, Black76 (Model.forward: spot-based vs quoted forward)
  methods/         PricingMethod ABC, registry; analytic.py + black_formulas.py (closed forms)
  risk/            bumps.py (market transforms), greeks.py (central-difference bump layer),
                   units.py (pure → desk units), scenarios.py (MarketShock, profiles, grids)
  calibration/     implied_vol.py (Let's Be Rational); Phase 3: SVI, Dupire, Heston
api/             FastAPI + pydantic v2. Thin: validate → map → engine.price → serialise.
  schemas.py       Request/response models (decimals, not %)
  mapping.py       The only place API schemas and engine types meet
  routes.py        /api/health, /api/meta, /api/price, /api/profile, /api/heatmap,
                   /api/implied-vol
  app.py           App factory; serves web/dist with SPA fallback when built
  openapi.json     Generated. Source of web/src/api/schema.d.ts
web/             React 19 + TS (strict) + Vite + Tailwind v4 + TanStack Query + Zustand
  src/api/         client.ts (fetch + abort + timing), schema.d.ts (generated), types.ts
  src/state/       inputs.ts (display units → toRequest), ui.ts (persisted prefs)
  src/state/       + compare.ts (pinned result for compare mode)
  src/components/  Panels, fields, command palette (cmdk), Radix primitives; Chart.tsx
                   (lazy Plotly, themed from CSS tokens), Profiles, Heatmap, CompareBar
  e2e/             Playwright smoke tests against the built single-process app
tests/           pytest: unit/, api/, perf/ (benchmarks, `-m perf`). Oracles (dev only): QuantLib,
                 mpmath (50-digit), py_lets_be_rational
docs/            conventions.md + one note per model/method
scripts/         launch.py (launchers), dump_openapi.py
```

**Dependency rule:** `engine` ← `api` ← `web`. The engine never imports pydantic, fastapi or
anything from `api` (enforced by `tests/unit/test_architecture.py`). QuantLib may be used only in
tests, as an oracle.

**Engine types** are frozen, slotted dataclasses. The API has its own pydantic schemas and maps them
in `api/mapping.py`.

## Adding things

- **New pricing method:**
  1. Subclass `engine.methods.base.PricingMethod`: `supports`, `evaluate`, optionally
     `analytic_greeks` (pure model units).
  2. Register it in `engine/methods/registry.py`.
  3. Add tests against an independent reference with stated tolerances, and a note in
     `docs/methods/`.
- **New instrument:** add a frozen `kw_only` dataclass under `engine/instruments/` with a
  `maturity` property, an API schema and mapping, then run `make openapi`.
- **New greek or market bump:** add the transform to `risk/bumps.py`, the stencil to
  `risk/greeks.py`, and the unit to `risk/units.py`. Update `docs/conventions.md` and the tooltip
  text in `web/src/lib/greeks.ts`.
- **API schema change:** run `make openapi` and commit both generated files. CI fails on drift.

## Conventions (summary; full detail in docs/conventions.md)

- **Dates:** ACT/365F. Weekday calendar with a pluggable holiday set. Valuation granularity is one
  day.
- **Forwards:** `F = S·P_q·P_b/P_r`. Repo/borrow `b` enters the forward only, never discounting.
- **Engine greeks:** pure model units (∂V/∂x, time in years). Θ = ∂V/∂t with spot, vol and rates
  held fixed.
- **Desk units:**
  - Cash: Δ·S·N; Γ·S²·N/100 per 1%; ν per vol pt; Θ per calendar day; ρ and φ per bp.
  - Pure: `100·cash/(N·S)`, i.e. % of notional.
- **Unit price** is per unit of underlying. % of notional = `100·price/S₀`.
- **Numbers:** no magic numbers in the engine. Settings go in `PricingSettings` and unit constants in
  `risk/units.py`.
- **Docstrings:** state the formula or a reference.

## UI rules

- Three columns: inputs (left), headline + analysis tabs (centre), greeks (right, always visible).
- Recompute live: 120 ms debounce, superseded requests aborted, previous result stays dimmed while
  pending.
- Keyboard first:
  - ⌘K / Ctrl K opens the command palette.
  - ↑/↓ nudge numeric fields (Shift ×10, Alt ×0.1). Esc reverts a field.
  - Arrow keys move segmented controls.
- **Typography:** Inter for UI; JetBrains Mono with tabular figures for numbers (the `num`
  utility), right-aligned, with a true minus sign.
- **Colours:** tokens are CSS variables in `web/src/index.css`, and light and dark are designed
  separately. One accent colour; red and green only for signed PnL.
- **Chart colours:** series use `--series-1..4`. That order passed the dataviz CVD validator in
  both themes; re-run it if you change them. PnL heatmaps use `--pnl-neg/mid/pos`.
- **No colour transitions:** theme switches must be instant.
- **Units:** every number shows its unit; units come from the API.
- **Analysis tabs:** a tab ships only with the phase that makes it useful.

## Running

```
make install     # uv sync + npm ci
make dev         # uvicorn --reload :8765 + vite :5173 (proxy /api), opens browser
make serve       # build if stale, single process on :8765, opens browser
./start.command  # macOS double-click (= serve); start.bat on Windows
make check       # lint + typecheck + unit tests (what CI runs, minus e2e)
make e2e         # Playwright smoke tests (builds first)
make bench       # performance benchmarks
make openapi     # regenerate api/openapi.json + web/src/api/schema.d.ts
```

- **Python:** 3.12, managed by uv (`.python-version`).
- **Node:** 20+ (CI uses 22).
- **Playwright:** `@playwright/test` is pinned to 1.56.1 to match the Chromium preinstalled in
  cloud sessions. CI runs `playwright install chromium`.

## Git

- One branch and PR per phase (or per sub-feature). Conventional commits. Never push to `main`.
- CI must be green before asking for review.
- CI jobs: python (ruff, mypy, pytest with the hypothesis `ci` profile, OpenAPI drift), web
  (eslint, prettier, tsc, vitest, build, TS-types drift), e2e (Playwright), perf (informational).

## Current state

- **Phase 0 (foundations):** done, merged.
- **Phase 1 (vanilla, done perfectly):**
  - BSM and Black-76 closed forms with all nine greeks.
  - Let's Be Rational implied vol.
  - Profiles, Heatmap and Diagnostics tabs (including the greek check).
  - Implied-vol solver in the UI.
  - Compare mode (pin).
  - Performance: price plus greeks ~20 µs; 50×50 heatmap ~36 ms.
- **Next, Phase 2:** American options (Leisen–Reimer tree plus Crank–Nicolson PDE side by side),
  digitals, discrete dividends, and rate/dividend term structures.

## Testing policy

- **Independent references:** every pricer is tested against something outside itself, with stated
  tolerances (see `docs/`).
- **Finite-difference checks:** tolerances are derived from error terms (Richardson residual vs the
  removed h² term, plus ε·(V + S)/stencil round-off), not tuned until green.
- **Conditioning:** property-test domains exclude inputs the problem can't resolve (subnormal
  prices, OTM parts below round-off next to intrinsic). The exclusion and its reason are written
  down in the test.
- **Before pushing:** run a few extra `--hypothesis-seed` values for new property tests. CI uses
  the derandomised `ci` profile.

## Decision log

| Date | Decision | Reason |
|---|---|---|
| 2026-09-30 | Repo empty at start; scaffolded from scratch in `johnnyyammine/quant_pricing` | No prototype existed to audit |
| 2026-09-30 | Charts: Plotly, custom partial bundle (scatter, heatmap, contour, surface) | Only mature option with real 3D surfaces, heatmaps and built-in PNG export in one library. The partial bundle keeps size reasonable |
| 2026-09-30 | IV solver: own typed port of Jäckel's "Let's Be Rational" (Phase 1) | Machine precision in two iterations at all moneyness; brings an accurate normalised Black for deep-OTM prices. Oracles: `py_lets_be_rational`, QuantLib |
| 2026-09-30 | Engine uses frozen dataclasses; pydantic only in `api/` | Keeps the engine framework-free and strict-typed; no validation overhead in revaluation loops |
| 2026-09-30 | Pure greeks = % of notional; cash greeks in position currency (table in conventions.md) | Approved desk-unit definitions |
| 2026-09-30 | Θ = ∂V/∂t at fixed spot, vol and rates; bump version rolls the valuation date ±1 day, central | Matches the analytic definition to O(h²); one-sided with a warning within a day of maturity |
| 2026-09-30 | Vanilla sizing: quantity N of underlying units; % of notional = price/S₀ | Approved. Structured products carry an explicit notional |
| 2026-09-30 | Top-level packages `engine` and `api` from one root pyproject (hatchling) | Matches the agreed layout |
| 2026-09-30 | uv + npm; Python pinned to 3.12 | uv gives lockfile, Python install and speed; npm ships with Node |
| 2026-09-30 | Launchers run the built SPA from FastAPI (one process, one port); `make dev` uses Vite HMR | One-command start without two servers; dev keeps hot reload |
| 2026-09-30 | TS API types generated from OpenAPI (openapi-typescript), drift checked in CI | Front end and API cannot silently diverge |
| 2026-09-30 | Radix primitives + cmdk; self-hosted Inter and JetBrains Mono; Prettier for TS | Accessible unstyled primitives; works offline; consistent formatting |
| 2026-09-30 | Bumps cached per stencil point (19 revaluations for all nine greeks) | Shared points priced once |
| 2026-09-30 | Phase 1 plan approved; stub pricing method removed | Analytic BSM/Black-76 landed |
| 2026-09-30 | Plotly via the prebuilt `plotly.js-cartesian-dist-min` bundle, lazy-loaded (gl3d bundle for Phase 3 surfaces) | Building Plotly from source in Vite needs glslify transforms; the official partial bundle is the same code without that fragility |
| 2026-09-30 | Profiles and heatmaps go through generic full revaluation (`price()` per point), no vectorised kernel | 50×50 in ~36 ms, and it works for any future instrument/method unchanged |
| 2026-09-30 | Analytic Θ and charm only for flat curves and a flat surface; otherwise bumped | Closed forms assume time-homogeneous inputs |
| 2026-09-30 | Heatmap keeps red/green for signed PnL (user spec) with a neutral midpoint, lightness-separated poles, exact hover values and a labelled colour bar | The dataviz guidance prefers blue/red for colour-blindness; these mitigations keep the user's convention readable |
| 2026-09-30 | Default trade 10,000 units, 2% dividend yield | Cash greeks readable at €1m notional; avoids the degenerate d₂ = 0 case of r − q = σ²/2 |
| 2026-09-30 | Dev oracles: QuantLib, mpmath, py_lets_be_rational; scipy-stubs for strict mypy | Independent references; typed scipy |
