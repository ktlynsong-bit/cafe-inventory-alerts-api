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