import math
from dataclasses import replace

import pytest

from engine.errors import UnsupportedCombinationError
from engine.instruments.vanilla import OptionType
from engine.methods.intrinsic import ForwardIntrinsic
from engine.methods.registry import get_method, methods_for
from engine.models.base import Model
from engine.models.black_scholes import BlackScholesMerton
from engine.pricing import price
from engine.results import Greek


class OtherModel(Model):
    name = "other"


def test_unsupported_combination_raises(market, call):
    with pytest.raises(UnsupportedCombinationError):
        price(call, market, OtherModel(), ForwardIntrinsic())


def test_registry_lookup(call):
    assert isinstance(get_method("forward_intrinsic"), ForwardIntrinsic)
    assert [m.name for m in methods_for(call, BlackScholesMerton())] == ["forward_intrinsic"]
    with pytest.raises(KeyError, match="known"):
        get_method("nope")


@pytest.mark.parametrize("opt", list(OptionType))
def test_stub_intrinsic_value_and_parity(market, call, opt):
    inst = replace(call, option_type=opt)
    res = price(inst, market, BlackScholesMerton(), ForwardIntrinsic())
    t = market.time_to(inst.expiry)
    f, df = market.forward(t), market.df(t)
    assert res.price == pytest.approx(df * max(opt.omega * (f - inst.strike), 0.0), rel=1e-15)
    assert res.greeks is not None
    # ITM call: Δ = DF·F/S exactly (linear in S away from the kink)
    if opt is OptionType.CALL:
        assert res.greeks[Greek.DELTA] == pytest.approx(df * f / market.spot, rel=1e-9)
        assert res.greeks[Greek.VEGA] == 0.0
    assert math.isfinite(res.diagnostics.runtime_ms)
