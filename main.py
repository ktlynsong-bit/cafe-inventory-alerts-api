from fastapi import FastAPI, HTTPException
from typing import Literal
from pydantic import BaseModel, Field
from datetime import date
from fastapi import Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from database import SessionLocal, engine, Base
from database import ItemDB, UsageLogDB, SupplierDB

app = FastAPI(title="Cafe Inventory Alerts API")

Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def normalize_key_part(value: str | None) -> str:
    return (value or "").strip().lower()

def item_key(name: str, variant: str | None) -> str:
    return f"{normalize_key_part(name)}::{normalize_key_part(variant)}"


def item_row_to_dict(row: ItemDB) -> dict:
    return {
        "category": row.category,
        "name": row.name,
        "variant": row.variant,
        "material": row.material,
        "size_value": row.size_value,
        "size_unit": row.size_unit,
        "measure_unit": row.measure_unit,
        "quantity_on_hand": row.quantity_on_hand,
        "reorder_point": row.reorder_point,
        "lead_time_days": row.lead_time_days,
        "expiration_date": row.expiration_date,
    }

def usage_log_row_to_dict(row: UsageLogDB) -> dict:
    return {
        "item_name": row.item_name,
        "item_variant": row.item_variant,
        "quantity_used": row.quantity_used,
        "date": row.date,
    }

def supplier_row_to_dict(row: SupplierDB) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "contact_name": row.contact_name,
        "contact_email": row.contact_email,
        "contact_phone": row.contact_phone,
        "lead_time_days": row.lead_time_days,
        "notes": row.notes,
    }

def build_usage_stats(rows: list[UsageLogDB]) -> tuple[dict[str, float], dict[str, set[date]]]:
    totals: dict[str, float] = {}
    days: dict[str, set[date]] = {}

    for row in rows:
        key = item_key(row.item_name, row.item_variant)
        totals[key] = totals.get(key, 0) + row.quantity_used
        days.setdefault(key, set()).add(row.date)

    return totals, days

def find_item_row(db: Session, item_name: str, item_variant: str | None) -> ItemDB | None:
    normalized_name = normalize_key_part(item_name)
    normalized_variant = normalize_key_part(item_variant)

    query = db.query(ItemDB).filter(func.lower(func.trim(ItemDB.name)) == normalized_name)

    if normalized_variant:
        query = query.filter(func.lower(func.trim(ItemDB.variant)) == normalized_variant)
    else:
        query = query.filter(
            or_(
                ItemDB.variant.is_(None),
                func.trim(ItemDB.variant) == "",
                func.lower(func.trim(ItemDB.variant)) == "",
            )
        )

    return query.first()

Category = Literal[
    "cups", "lids", "straws", "sleeves", "carriers", "napkins",
    "sugar", "syrup", "beans", "milk"
]
MeasureUnit = Literal["count", "fl_oz", "lb", "liter", "packet"]

class Item(BaseModel):
    category: Category
    name: str
    variant: str | None = None            # e.g. "12oz", "vanilla", "oat"
    material: str | None = None           # e.g. "paper", "plastic"
    size_value: float | None = None       # e.g. 12
    size_unit: str | None = None          # e.g. "oz"
    measure_unit: MeasureUnit             # how stock is measured
    quantity_on_hand: float = Field(ge=0)
    reorder_point: float = Field(ge=0)
    lead_time_days: int = Field(ge=0)
    expiration_date: date | None = None   # mainly milk/beans/syrups

class UsageLog(BaseModel):
    item_name: str
    item_variant: str | None = None
    quantity_used: float = Field(gt=0)
    date: date

class BulkItemsRequest(BaseModel):
    items: list[Item]


class SupplierCreate(BaseModel):
    name: str
    contact_name: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    lead_time_days: int = Field(ge=0, default=0)
    notes: str | None = None


class SupplierUpdate(BaseModel):
    name: str | None = None
    contact_name: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    lead_time_days: int | None = Field(ge=0, default=None)
    notes: str | None = None


@app.get("/", response_class=HTMLResponse)
def homepage():
    return """
<!doctype html>
<html lang=\"en\">
  <head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <title>Cafe Inventory Alerts API</title>
    <style>
      body { font-family: -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif; margin: 2rem; color: #1a1a1a; }
      .card { max-width: 760px; border: 1px solid #e8e8e8; border-radius: 12px; padding: 1.25rem; }
      h1 { margin-top: 0; }
      ul { line-height: 1.7; }
      code { background: #f6f6f6; padding: 0.1rem 0.3rem; border-radius: 6px; }
    </style>
  </head>
  <body>
    <div class=\"card\">
      <h1>Cafe Inventory Alerts API</h1>
      <p>Backend API for inventory tracking, usage logging, and analytics.</p>
      <ul>
        <li>Health: <a href=\"/health\">/health</a></li>
        <li>Interactive docs: <a href=\"/docs\">/docs</a></li>
        <li>Example endpoint: <code>/alerts/low-stock</code></li>
        <li>New endpoint group: <code>/suppliers</code></li>
      </ul>
    </div>
  </body>
</html>
"""

@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/suppliers")
def create_supplier(payload: SupplierCreate, db: Session = Depends(get_db)):
    normalized_name = normalize_key_part(payload.name)
    existing = (
        db.query(SupplierDB)
        .filter(func.lower(func.trim(SupplierDB.name)) == normalized_name)
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="Supplier already exists")

    row = SupplierDB(**payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"message": "supplier created", "supplier": supplier_row_to_dict(row)}


@app.get("/suppliers")
def list_suppliers(db: Session = Depends(get_db)):
    rows = db.query(SupplierDB).order_by(func.lower(SupplierDB.name).asc()).all()
    suppliers = [supplier_row_to_dict(row) for row in rows]
    return {"count": len(suppliers), "suppliers": suppliers}


@app.get("/suppliers/{supplier_id}")
def get_supplier(supplier_id: int, db: Session = Depends(get_db)):
    row = db.query(SupplierDB).filter(SupplierDB.id == supplier_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return {"supplier": supplier_row_to_dict(row)}


@app.put("/suppliers/{supplier_id}")
def update_supplier(supplier_id: int, payload: SupplierUpdate, db: Session = Depends(get_db)):
    row = db.query(SupplierDB).filter(SupplierDB.id == supplier_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Supplier not found")

    updates = payload.model_dump(exclude_unset=True)

    if "name" in updates:
        normalized_name = normalize_key_part(updates["name"])
        existing = (
            db.query(SupplierDB)
            .filter(func.lower(func.trim(SupplierDB.name)) == normalized_name)
            .filter(SupplierDB.id != supplier_id)
            .first()
        )
        if existing:
            raise HTTPException(status_code=409, detail="Supplier already exists")

    for field_name, value in updates.items():
        setattr(row, field_name, value)

    db.commit()
    db.refresh(row)
    return {"message": "supplier updated", "supplier": supplier_row_to_dict(row)}


@app.delete("/suppliers/{supplier_id}")
def delete_supplier(supplier_id: int, db: Session = Depends(get_db)):
    row = db.query(SupplierDB).filter(SupplierDB.id == supplier_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Supplier not found")

    deleted = supplier_row_to_dict(row)
    db.delete(row)
    db.commit()
    return {"message": "supplier deleted", "supplier": deleted}

@app.post("/items/bulk")
def create_items_bulk(payload: BulkItemsRequest, db: Session = Depends(get_db)):
    rows = [ItemDB(**item.model_dump()) for item in payload.items]
    db.add_all(rows)
    db.commit()
    return {"message": "bulk items created", "count": len(payload.items)}

@app.post("/items")
def create_item(item: Item, db: Session = Depends(get_db)):
    row = ItemDB(**item.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"message": "item created", "item": item}

@app.get("/items")
def list_items(db: Session = Depends(get_db)):
    rows = db.query(ItemDB).all()
    items_out = [item_row_to_dict(row) for row in rows]
    return {"count": len(items_out), "items": items_out}


@app.post("/usage-logs")
def log_usage(log: UsageLog, db: Session = Depends(get_db)):
    row = find_item_row(db, log.item_name, log.item_variant)
    if not row:
        raise HTTPException(status_code=404, detail="Item+variant not found")

    if log.quantity_used > row.quantity_on_hand:
        raise HTTPException(status_code=400, detail="Not enough stock available")

    row.quantity_on_hand -= log.quantity_used
    usage_row = UsageLogDB(**log.model_dump())
    db.add(usage_row)
    db.commit()
    db.refresh(row)
    return {"message": "usage logged", "item": item_row_to_dict(row)}

@app.get("/analytics/burn-rate")
def calculate_burn_rate(db: Session = Depends(get_db)):
    rows = db.query(UsageLogDB).all()
    if not rows:
        return {"count": 0, "items": []}

    totals, days = build_usage_stats(rows)

    results = []
    for key, total_used in totals.items():
        item_name, item_variant = key.split("::", 1)
        days_tracked = max(1, len(days[key]))
        avg_daily_usage = round(total_used / days_tracked, 2)

        results.append(
            {
                "item_name": item_name,
                "item_variant": item_variant or None,
                "total_used": total_used,
                "days_tracked": days_tracked,
                "avg_daily_usage": avg_daily_usage,
            }
        )

    return {"count": len(results), "items": results}

@app.get("/usage-logs")
def list_usage_logs(db: Session = Depends(get_db)):
    rows = db.query(UsageLogDB).all()
    logs_out = [usage_log_row_to_dict(row) for row in rows]
    return {"count": len(logs_out), "usage_logs": logs_out}

@app.get("/alerts/low-stock")
def low_stock_alerts(db: Session = Depends(get_db)):
    rows = db.query(ItemDB).filter(ItemDB.quantity_on_hand <= ItemDB.reorder_point).all()
    low_items = [item_row_to_dict(row) for row in rows]
    return {
        "count": len(low_items),
        "items": low_items
    }

@app.get("/alerts/expiration-risk")
def expiration_risk_alerts(days_ahead: int = 14, db: Session = Depends(get_db)):
    today = date.today()
    cutoff_date = date.fromordinal(today.toordinal() + days_ahead)
    rows = (
        db.query(ItemDB)
        .filter(ItemDB.expiration_date.isnot(None))
        .filter(ItemDB.expiration_date <= cutoff_date)
        .order_by(ItemDB.expiration_date.asc())
        .all()
    )

    risky_items = []
    for row in rows:
        if row.expiration_date is None:
            continue

        risky_items.append(
            {
                **item_row_to_dict(row),
                "days_until_expiration": (row.expiration_date - today).days,
            }
        )

    return {
        "count": len(risky_items),
        "days_ahead": days_ahead,
        "items": risky_items,
    }

@app.put("/items/{item_name}/{variant}")
def update_item(item_name: str, variant: str, item: Item, db: Session = Depends(get_db)):
    row = find_item_row(db, item_name, variant)
    if not row:
        raise HTTPException(status_code=404, detail="Item+variant not found")

    for field_name, value in item.model_dump().items():
        setattr(row, field_name, value)

    db.commit()
    db.refresh(row)
    return {"message": "item updated", "item": item_row_to_dict(row)}

@app.delete("/items/{item_name}/{variant}")
def delete_item(item_name: str, variant: str, db: Session = Depends(get_db)):
    row = find_item_row(db, item_name, variant)
    if not row:
        raise HTTPException(status_code=404, detail="Item+variant not found")

    deleted_item = item_row_to_dict(row)
    db.delete(row)
    db.commit()
    return {"message": "item deleted", "item": deleted_item}

@app.get("/analytics/reorder-suggestions")
def reorder_suggestions(db: Session = Depends(get_db)):
    usage_rows = db.query(UsageLogDB).all()
    item_rows = db.query(ItemDB).all()

    totals, days = build_usage_stats(usage_rows)

    avg_usage: dict[str, float] = {}
    for key, total_used in totals.items():
        days_tracked = max(1, len(days[key]))
        avg_usage[key] = total_used / days_tracked

    suggestions = []
    target_days = 14

    for row in item_rows:
        key = item_key(row.name, row.variant)
        daily = avg_usage.get(key, 0)

        if daily > 0:
            days_left = round(row.quantity_on_hand / daily, 2)
            suggested_qty = max(0, round((daily * target_days) - row.quantity_on_hand, 2))
        else:
            days_left = None
            suggested_qty = 0

        reorder_now = (
            row.quantity_on_hand <= row.reorder_point
            or (days_left is not None and days_left <= row.lead_time_days)
        )

        suggestions.append(
            {
                "item_name": row.name,
                "item_variant": row.variant,
                "quantity_on_hand": row.quantity_on_hand,
                "reorder_point": row.reorder_point,
                "avg_daily_usage": round(daily, 2) if daily > 0 else 0,
                "days_left": days_left,
                "lead_time_days": row.lead_time_days,
                "reorder_now": reorder_now,
                "suggested_reorder_quantity": suggested_qty,
            }
        )
    return {"count": len(suggestions), "suggestions": suggestions}


@app.get("/analytics/stockout-forecast")
def stockout_forecast(horizon_days: int = 30, db: Session = Depends(get_db)):
    if horizon_days < 1:
        raise HTTPException(status_code=400, detail="horizon_days must be >= 1")

    usage_rows = db.query(UsageLogDB).all()
    item_rows = db.query(ItemDB).all()

    totals, days = build_usage_stats(usage_rows)

    avg_usage: dict[str, float] = {}
    for key, total_used in totals.items():
        days_tracked = max(1, len(days[key]))
        avg_usage[key] = total_used / days_tracked

    forecasts = []
    for row in item_rows:
        key = item_key(row.name, row.variant)
        daily = avg_usage.get(key, 0)

        if daily > 0:
            days_until_stockout = round(row.quantity_on_hand / daily, 2)
            projected_quantity = round(row.quantity_on_hand - (daily * horizon_days), 2)
            will_stockout = days_until_stockout <= horizon_days
            projected_shortage = round(abs(projected_quantity), 2) if projected_quantity < 0 else 0
        else:
            days_until_stockout = None
            projected_quantity = row.quantity_on_hand
            will_stockout = False
            projected_shortage = 0

        forecasts.append(
            {
                "item_name": row.name,
                "item_variant": row.variant,
                "quantity_on_hand": row.quantity_on_hand,
                "avg_daily_usage": round(daily, 2) if daily > 0 else 0,
                "horizon_days": horizon_days,
                "days_until_stockout": days_until_stockout,
                "will_stockout_within_horizon": will_stockout,
                "projected_quantity_at_horizon": projected_quantity,
                "projected_shortage_at_horizon": projected_shortage,
            }
        )

    forecasts.sort(
        key=lambda x: (
            not x["will_stockout_within_horizon"],
            x["days_until_stockout"] is None,
            x["days_until_stockout"] if x["days_until_stockout"] is not None else 10**9,
        )
    )

    return {"count": len(forecasts), "horizon_days": horizon_days, "items": forecasts}
