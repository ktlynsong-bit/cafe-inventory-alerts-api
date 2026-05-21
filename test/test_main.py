from fastapi.testclient import TestClient
from main import app, items, usage_logs

client = TestClient(app)


def reset_state():
    items.clear()
    usage_logs.clear()


def test_health():
    reset_state()
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_create_and_list_items():
    reset_state()
    payload = {
        "category": "cups",
        "name": "Cup",
        "variant": "12oz",
        "material": "paper",
        "size_value": 12,
        "size_unit": "oz",
        "measure_unit": "count",
        "quantity_on_hand": 100,
        "reorder_point": 20,
        "lead_time_days": 5,
        "expiration_date": None
    }

    create_res = client.post("/items", json=payload)
    assert create_res.status_code == 200

    list_res = client.get("/items")
    assert list_res.status_code == 200
    body = list_res.json()
    assert body["count"] == 1
    assert body["items"][0]["name"] == "Cup"


def test_usage_log_reduces_stock():
    reset_state()
    item_payload = {
        "category": "cups",
        "name": "Cup",
        "variant": "12oz",
        "material": "paper",
        "size_value": 12,
        "size_unit": "oz",
        "measure_unit": "count",
        "quantity_on_hand": 100,
        "reorder_point": 20,
        "lead_time_days": 5,
        "expiration_date": None
    }
    client.post("/items", json=item_payload)

    usage_payload = {
        "item_name": "Cup",
        "item_variant": "12oz",
        "quantity_used": 10,
        "date": "2026-05-21"
    }
    log_res = client.post("/usage-logs", json=usage_payload)
    assert log_res.status_code == 200

    items_res = client.get("/items")
    stock = items_res.json()["items"][0]["quantity_on_hand"]
    assert stock == 90


def test_low_stock_alerts():
    reset_state()
    client.post("/items", json={
        "category": "cups",
        "name": "Cup",
        "variant": "16oz",
        "material": "paper",
        "size_value": 16,
        "size_unit": "oz",
        "measure_unit": "count",
        "quantity_on_hand": 10,
        "reorder_point": 20,
        "lead_time_days": 5,
        "expiration_date": None
    })

    res = client.get("/alerts/low-stock")
    assert res.status_code == 200
    body = res.json()
    assert body["count"] == 1
    assert body["items"][0]["variant"] == "16oz"


def test_burn_rate_returns_data():
    reset_state()
    client.post("/items", json={
        "category": "cups",
        "name": "Cup",
        "variant": "20oz",
        "material": "paper",
        "size_value": 20,
        "size_unit": "oz",
        "measure_unit": "count",
        "quantity_on_hand": 100,
        "reorder_point": 20,
        "lead_time_days": 5,
        "expiration_date": None
    })

    client.post("/usage-logs", json={
        "item_name": "Cup",
        "item_variant": "20oz",
        "quantity_used": 10,
        "date": "2026-05-20"
    })
    client.post("/usage-logs", json={
        "item_name": "Cup",
        "item_variant": "20oz",
        "quantity_used": 20,
        "date": "2026-05-21"
    })

    res = client.get("/analytics/burn-rate")
    assert res.status_code == 200
    body = res.json()
    assert body["count"] >= 1
    assert "avg_daily_usage" in body["items"][0]