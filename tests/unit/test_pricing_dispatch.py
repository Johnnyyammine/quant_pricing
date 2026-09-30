import pytest

from engine.errors import UnsupportedCombinationError
from engine.methods.analytic import AnalyticBlack
from engine.methods.registry import get_method, methods_for
from engine.models.base import Model
from engine.models.black76 import Black76
from engine.models.black_scholes import BlackScholesMerton
from engine.pricing import price


class OtherModel(Model):
    name = "other"


def test_unsupported_combination_raises(market, call):
    with pytest.raises(UnsupportedCombinationError):
        price(call, market, OtherModel(), AnalyticBlack())


@pytest.mark.parametrize("model", [BlackScholesMerton(), Black76()])
def test_registry_lookup(call, model):
    assert isinstance(get_method("analytic"), AnalyticBlack)
    assert [m.name for m in methods_for(call, model)] == ["analytic"]


def test_unknown_method():
    with pytest.raises(KeyError, match="known"):
        get_method("nope")


def test_model_forward(market):
    assert BlackScholesMerton().forward(market, 1.0) == market.forward(1.0)
    assert Black76().forward(market, 1.0) == market.spot
