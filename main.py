from fastapi import FastAPI, HTTPException
from typing import Literal
from pydantic import BaseModel, Field
from datetime import date

app = FastAPI(title="Cafe Inventory Alerts API")

def item_key(name: str, variant: str | None) -> str:
    return f"{name.strip().lower()}::{(variant or '').strip().lower()}"

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
items: list[Item] = []

class UsageLog(BaseModel):
    item_name: str
    item_variant: str | None = None
    quantity_used: float = Field(gt=0)
    date: date

usage_logs: list[UsageLog] = []    

class BulkItemsRequest(BaseModel):
    items: list[Item]

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.post("/items/bulk")
def create_items_bulk(payload: BulkItemsRequest):
    items.extend(payload.items)
    return {"message": "bulk items created", "count": len(payload.items)}

@app.post("/items")
def create_item(item: Item):
    items.append(item)
    return {"message": "item created", "item": item}

@app.get("/items")
def list_items():
    return {"count": len(items), "items": items}

@app.post("/usage-logs")
def log_usage(log: UsageLog):
    target_key = item_key(log.item_name, log.item_variant)

    for item in items:
        if item_key(item.name, item.variant) == target_key:
            if log.quantity_used > item.quantity_on_hand:
                raise HTTPException(
                    status_code=400,
                    detail="Not enough stock available"
                )
            item.quantity_on_hand -= log.quantity_used
            usage_logs.append(log)
            return {"message": "usage logged", "item": item}

    raise HTTPException(status_code=404, detail="Item+variant not found")

@app.get("/analytics/burn-rate")
def calculate_burn_rate():
    if not usage_logs:
        return {"count": 0, "items": []}

    totals = {}
    days = {}

    for log in usage_logs:
        key = item_key(log.item_name, log.item_variant)
        totals[key] = totals.get(key, 0) + log.quantity_used
        days.setdefault(key, set()).add(log.date)

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
def list_usage_logs():
    return {"count": len(usage_logs), "usage_logs": usage_logs}

@app.get("/alerts/low-stock")
def low_stock_alerts():
    low_items = [item for item in items if item.quantity_on_hand <= item.reorder_point]
    return {
        "count": len(low_items),
        "items": low_items
    }