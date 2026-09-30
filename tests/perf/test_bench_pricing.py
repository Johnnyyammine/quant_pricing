"""Performance benchmarks (`make bench`). Targets are asserted from Phase 1 onwards."""

import pytest

from engine.methods.intrinsic import ForwardIntrinsic
from engine.models.black_scholes import BlackScholesMerton
from engine.pricing import price

pytestmark = pytest.mark.perf


def test_bench_price_with_bump_greeks(benchmark, market, call):
    result = benchmark(price, call, market, BlackScholesMerton(), ForwardIntrinsic())
    assert result.greeks is not None
