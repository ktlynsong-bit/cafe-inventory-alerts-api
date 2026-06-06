from fastapi.testclient import TestClient
from database import SessionLocal, ItemDB, UsageLogDB
from main import app

client = TestClient(app)


def reset_state():
    db = SessionLocal()
    try:
        db.query(UsageLogDB).delete()
        db.query(ItemDB).delete()
        db.commit()
    finally:
        db.close()


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


def test_expiration_risk_alerts_returns_near_expiry_items():
    reset_state()
    client.post("/items", json={
        "category": "milk",
        "name": "Oat Milk",
        "variant": "Barista",
        "material": "carton",
        "size_value": 64,
        "size_unit": "fl_oz",
        "measure_unit": "liter",
        "quantity_on_hand": 8,
        "reorder_point": 2,
        "lead_time_days": 3,
        "expiration_date": "2026-06-08"
    })

    client.post("/items", json={
        "category": "beans",
        "name": "Espresso Beans",
        "variant": "House",
        "material": "bag",
        "size_value": 5,
        "size_unit": "lb",
        "measure_unit": "lb",
        "quantity_on_hand": 12,
        "reorder_point": 4,
        "lead_time_days": 7,
        "expiration_date": "2026-07-20"
    })

    res = client.get("/alerts/expiration-risk?days_ahead=7")
    assert res.status_code == 200

    body = res.json()
    assert body["count"] == 1
    assert body["days_ahead"] == 7
    assert body["items"][0]["name"] == "Oat Milk"
    assert body["items"][0]["days_until_expiration"] == 3


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


def test_reorder_suggestions_returns_expected_fields():
    reset_state()
    client.post("/items", json={
        "category": "cups",
        "name": "Cup",
        "variant": "12oz",
        "material": "paper",
        "size_value": 12,
        "size_unit": "oz",
        "measure_unit": "count",
        "quantity_on_hand": 10,
        "reorder_point": 20,
        "lead_time_days": 5,
        "expiration_date": None
    })

    client.post("/usage-logs", json={
        "item_name": "Cup",
        "item_variant": "12oz",
        "quantity_used": 5,
        "date": "2026-05-20"
    })
    client.post("/usage-logs", json={
        "item_name": "Cup",
        "item_variant": "12oz",
        "quantity_used": 5,
        "date": "2026-05-21"
    })

    res = client.get("/analytics/reorder-suggestions")
    assert res.status_code == 200
    body = res.json()
    assert body["count"] >= 1

    suggestion = body["suggestions"][0]
    assert "item_name" in suggestion
    assert "item_variant" in suggestion
    assert "avg_daily_usage" in suggestion
    assert "days_left" in suggestion
    assert "reorder_now" in suggestion
    assert "suggested_reorder_quantity" in suggestion