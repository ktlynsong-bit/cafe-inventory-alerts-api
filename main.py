from fastapi import FastAPI

app = FastAPI(title="Cafe Inventory Alerts API")

@app.get("/health")
def health_check():
    return {"status": "ok"}