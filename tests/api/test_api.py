import pytest
from fastapi.testclient import TestClient

from api.app import create_app

REQUEST = {
    "instrument": {
        "type": "european",
        "option_type": "call",
        "strike": 95.0,
        "expiry": "2027-01-02",
        "quantity": 10.0,
        "currency": "EUR",
    },
    "market": {
        "valuation_date": "2026-01-02",
        "spot": 100.0,
        "rate": 0.03,
        "dividend_yield": 0.01,
        "borrow": 0.0,
        "vol": 0.2,
    },
}


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app(web_dist=None))


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_meta_lists_methods(client):
    names = [m["name"] for m in client.get("/api/meta").json()["methods"]]
    assert names == ["analytic", "lr_tree", "cn_pde"]


def test_price_round_trip(client):
    r = client.post("/api/price", json=REQUEST)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["currency"] == "EUR"
    assert body["position_value"] == pytest.approx(10 * body["price"])
    assert body["pct_notional"] == pytest.approx(100 * body["price"] / 100.0)
    keys = [g["key"] for g in body["greeks"]["cash"]]
    assert keys[:3] == ["delta", "gamma", "vega"]
    assert [g["key"] for g in body["greeks"]["pure"]] == keys
    assert body["diagnostics"]["settings"]["bumps"]["spot_rel"] > 0
    assert body["diagnostics"]["method_label"]


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("market", "spot"), -1.0),
        (("market", "vol"), 0.0),
        (("instrument", "strike"), 0.0),
        (("instrument", "option_type"), "straddle"),
    ],
)
def test_invalid_inputs_are_422(client, path, value):
    req = {k: dict(v) for k, v in REQUEST.items()}
    req[path[0]][path[1]] = value
    assert client.post("/api/price", json=req).status_code == 422


def test_unknown_method_is_422(client):
    r = client.post("/api/price", json={**REQUEST, "method": "nope"})
    assert r.status_code == 422
    assert "known" in r.json()["detail"]


def test_expired_option_is_422(client):
    req = {k: dict(v) for k, v in REQUEST.items()}
    req["instrument"]["expiry"] = "2025-01-02"
    r = client.post("/api/price", json=req)
    assert r.status_code == 422
    assert "matured" in r.json()["detail"]


def test_extra_fields_rejected(client):
    req = {k: dict(v) for k, v in REQUEST.items()}
    req["market"]["sopt"] = 1.0
    assert client.post("/api/price", json=req).status_code == 422


def test_spa_serving_and_no_path_traversal(tmp_path):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html>spa</html>")
    (dist / "favicon.svg").write_text("<svg/>")
    (tmp_path / "secret.txt").write_text("secret")
    c = TestClient(create_app(web_dist=dist))
    assert c.get("/").text == "<html>spa</html>"
    assert c.get("/deep/link").text == "<html>spa</html>"
    assert c.get("/favicon.svg").text == "<svg/>"
    for probe in ("/../secret.txt", "/%2e%2e/secret.txt", "/..%2fsecret.txt"):
        assert "secret" not in c.get(probe).text, probe
    assert c.get("/api/health").json()["status"] == "ok"


def _req(**changes):
    req = {k: dict(v) for k, v in REQUEST.items()}
    for (section, key), value in changes.items():
        req[section][key] = value
    return req


def test_price_black76_uses_quoted_forward(client):
    body = client.post("/api/price", json={**REQUEST, "model": {"type": "black76"}}).json()
    assert body["forward"] == pytest.approx(REQUEST["market"]["spot"])
    phi = next(g for g in body["greeks"]["cash"] if g["key"] == "phi")
    assert phi["value"] == 0.0


def test_force_bump_greeks_round_trips(client):
    req = {**REQUEST, "settings": {"force_bump_greeks": True}}
    body = client.post("/api/price", json=req).json()
    assert {g["source"] for g in body["greeks"]["cash"]} == {"bump"}
    assert body["diagnostics"]["settings"]["force_bump_greeks"] is True


def test_profile_spot_axis(client):
    req = {"pricing": REQUEST, "axis": "spot", "points": 11, "horizons_days": [0, 180, 9999]}
    body = client.post("/api/profile", json=req).json()
    assert len(body["x"]) == 11
    assert body["x"][5] == pytest.approx(100.0)
    assert [s["label"] for s in body["series"]] == ["Today", "+180d", "Expiry"]
    today, expiry = body["series"][0], body["series"][-1]
    assert today["position_value"][5] == pytest.approx(
        client.post("/api/price", json=REQUEST).json()["position_value"]
    )
    # At expiry the value is the payoff.
    assert expiry["position_value"] == pytest.approx(body["payoff"])
    assert len(today["greeks"]["cash"]["delta"]) == 11
    assert body["units"]["pure"]["delta"] == "%"


def test_profile_time_axis(client):
    req = {"pricing": REQUEST, "axis": "time", "points": 13, "spot_shifts_pct": [-10, 0, 10]}
    body = client.post("/api/profile", json=req).json()
    assert body["x"][0] == 365.0
    assert body["x"][-1] == 0.0
    assert [s["label"] for s in body["series"]] == ["Spot -10%", "Spot", "Spot +10%"]


def test_heatmap_centre_is_base_value(client):
    req = {"pricing": REQUEST, "spot_steps": 5, "vol_steps": 5, "vol_range_pts": 30}
    body = client.post("/api/heatmap", json=req).json()
    assert len(body["values"]) == 5
    assert len(body["values"][0]) == 5
    assert body["values"][2][2] == pytest.approx(body["base_value"])
    # vol 20% − 30 pts is out of domain
    assert body["values"][0] == [None] * 5


def test_heatmap_horizon_beyond_expiry_is_422(client):
    r = client.post("/api/heatmap", json={"pricing": REQUEST, "horizon_days": 400})
    assert r.status_code == 422


@pytest.mark.parametrize("model", ["bsm", "black76"])
def test_implied_vol_recovers_input_vol(client, model):
    priced = client.post("/api/price", json={**REQUEST, "model": {"type": model}}).json()
    req = {k: v for k, v in REQUEST.items()} | {"model": {"type": model}}
    req["target_price"] = priced["price"]
    body = client.post("/api/implied-vol", json=req).json()
    assert body["implied_vol"] == pytest.approx(0.2, rel=1e-12)


def test_implied_vol_below_intrinsic_is_422(client):
    r = client.post("/api/implied-vol", json={**REQUEST, "target_price": 1.0})
    assert r.status_code == 422
    assert "intrinsic" in r.json()["detail"]
