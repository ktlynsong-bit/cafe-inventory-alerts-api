from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from datetime import date

app = FastAPI(title="Cafe Inventory Alerts API")

class Item(BaseModel):
    name: str
    unit: str
    current_stock: int
    minimum_stock: int

items: list[Item] = []

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.post("/items")
def create_item(item: Item):
    items.append(item)
    return {"message": "item created", "item": item}

@app.get("/items")
def list_items():
    return {"count": len(items), "items": items}

@app.get("/alerts/low-stock")
def low_stock_alerts():
    low_items = [item for item in items if item.current_stock <= item.minimum_stock]
    return {
        "count": len(low_items),
        "items": low_items
    }

class UsageLog(BaseModel):
    item_name: str
    quantity_used: int
    date: date

usage_logs: list[UsageLog] = []    

@app.post("/usage-logs")
def log_usage(log: UsageLog):
    for item in items:
        if item.name == log.item_name:
            if log.quantity_used > item.current_stock:
                raise HTTPException(
                    status_code=400,
                    detail="Not enough stock available"
                )
            item.current_stock -= log.quantity_used
            usage_logs.append(log)
            return {"message": "usage logged", "item": item}
    raise HTTPException(status_code=404, detail="Item not found")

@app.get("/usage-logs")
def list_usage_logs():
    return {"count": len(usage_logs), "usage_logs": usage_logs}

@app.get("/analytics/burn-rate")
def calculate_burn_rate():
    if not usage_logs:
        return {"count": 0, "items": []}

    totals = {}
    dates = {}

    for log in usage_logs:
        totals[log.item_name] = totals.get(log.item_name, 0) + log.quantity_used
        dates.setdefault(log.item_name, set()).add(log.date)

    results = []
    for item_name, total_used in totals.items():
        days_tracked = max(1, len(dates[item_name]))
        avg_daily_usage = round(total_used / days_tracked, 2)
        results.append(
            {
                "item_name": item_name,
                "total_used": total_used,
                "days_tracked": days_tracked,
                "avg_daily_usage": avg_daily_usage,
            }
        )

    return {"count": len(results), "items": results}