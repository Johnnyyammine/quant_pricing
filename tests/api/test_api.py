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
    assert "forward_intrinsic" in names


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
