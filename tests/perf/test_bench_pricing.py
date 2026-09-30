"""Performance targets (`make bench`). Asserted on the median to stay robust on shared runners."""

import pytest

from engine.methods.analytic import AnalyticBlack
from engine.models.black_scholes import BlackScholesMerton
from engine.pricing import price
from engine.settings import PricingSettings

pytestmark = pytest.mark.perf

VANILLA_TARGET_S = 5e-3


def test_vanilla_price_and_all_greeks_under_5ms(benchmark, market, call):
    result = benchmark(price, call, market, BlackScholesMerton(), AnalyticBlack())
    assert result.greeks is not None
    assert benchmark.stats.stats.median < VANILLA_TARGET_S


def test_bump_greeks_reference(benchmark, market, call):
    settings = PricingSettings(force_bump_greeks=True)
    benchmark(price, call, market, BlackScholesMerton(), AnalyticBlack(), settings)


HEATMAP_TARGET_S = 1.0


def test_heatmap_50x50_under_1s(benchmark, market, call):
    from engine.risk.scenarios import spot_value_grid

    shifts = [-0.5 + i / 49 for i in range(50)]
    vols = [-0.1 + 0.2 * i / 49 for i in range(50)]
    grid = benchmark.pedantic(
        spot_value_grid,
        args=(call, market, BlackScholesMerton(), AnalyticBlack(), PricingSettings(), shifts, vols),
        rounds=5,
    )
    assert len(grid) == 50
    assert benchmark.stats.stats.median < HEATMAP_TARGET_S
