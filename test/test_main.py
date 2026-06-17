from fastapi.testclient import TestClient
from datetime import date, timedelta
from database import SessionLocal, ItemDB, UsageLogDB, SupplierDB
from main import app

client = TestClient(app)


def reset_state():
    db = SessionLocal()
    try:
        db.query(UsageLogDB).delete()
        db.query(ItemDB).delete()
        db.query(SupplierDB).delete()
        db.commit()
    finally:
        db.close()


def test_health():
    reset_state()
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_homepage_returns_html():
    reset_state()
    res = client.get("/")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
    assert "Cafe Inventory Alerts API" in res.text


def test_supplier_crud_flow():
    reset_state()

    create_res = client.post("/suppliers", json={
        "name": "Metro Food Supply",
        "contact_name": "Ari Lee",
        "contact_email": "ari@metro.example",
        "contact_phone": "555-0102",
        "lead_time_days": 4,
        "notes": "Morning delivery preferred"
    })
    assert create_res.status_code == 200
    created = create_res.json()["supplier"]
    supplier_id = created["id"]
    assert created["name"] == "Metro Food Supply"

    list_res = client.get("/suppliers")
    assert list_res.status_code == 200
    assert list_res.json()["count"] == 1

    get_res = client.get(f"/suppliers/{supplier_id}")
    assert get_res.status_code == 200
    assert get_res.json()["supplier"]["contact_name"] == "Ari Lee"

    update_res = client.put(f"/suppliers/{supplier_id}", json={
        "lead_time_days": 6,
        "notes": "Deliver by 8am"
    })
    assert update_res.status_code == 200
    updated = update_res.json()["supplier"]
    assert updated["lead_time_days"] == 6
    assert updated["notes"] == "Deliver by 8am"

    delete_res = client.delete(f"/suppliers/{supplier_id}")
    assert delete_res.status_code == 200

    missing_res = client.get(f"/suppliers/{supplier_id}")
    assert missing_res.status_code == 404


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
    near_expiry = (date.today() + timedelta(days=3)).isoformat()
    safe_expiry = (date.today() + timedelta(days=30)).isoformat()

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
        "expiration_date": near_expiry
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
        "expiration_date": safe_expiry
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