from fastapi import FastAPI
from pydantic import BaseModel

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