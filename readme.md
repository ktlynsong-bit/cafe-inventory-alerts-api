# Cafe Inventory Alerts API

A backend API for cafe inventory operations built with FastAPI, SQLAlchemy, and SQLite.

This project tracks inventory items (cups, lids, milk, beans, syrups, etc.), records daily usage, and provides analytics endpoints for low-stock detection, burn-rate tracking, and reorder suggestions.

It is designed to be portfolio-ready: practical inventory workflows, analytics that resemble real cafe operations, and clear test coverage.

## Live API

- Base URL: https://cafe-inventory-alerts-api-production.up.railway.app/
- Health check: https://cafe-inventory-alerts-api-production.up.railway.app/health
- Interactive docs: https://cafe-inventory-alerts-api-production.up.railway.app/docs

## What This API Does

- Show a simple homepage at `/` with links to docs and key endpoints
- Create and manage detailed inventory items with category, variant, and stock metadata
- Create and manage supplier records with contact details and lead times
- Bulk import inventory records for fast setup
- Log daily item usage and automatically reduce stock on hand
- Flag low-stock items
- Flag items at expiration risk for perishable stock
- Calculate burn rate based on usage logs
- Generate reorder suggestions using stock, burn rate, reorder points, and lead time

## Tech Stack

- Python
- FastAPI
- SQLAlchemy ORM
- SQLite
- Pytest

## Project Structure

```text
cafe-inventory-alerts-api/
	main.py
	database.py
	cafe_inventory.db
	test/
		test_main.py
	example/
		post_items_bulk.json
		post_usage_logs.json
```

## Run Locally

```bash
cd /.../cafe-inventory-alerts-api
source .venv/bin/activate
fastapi dev main.py
```

API docs will be available at:

- Local: http://127.0.0.1:8000/docs
- Production: https://cafe-inventory-alerts-api-production.up.railway.app/docs

## Run Tests

```bash
cd /.../cafe-inventory-alerts-api
source .venv/bin/activate
python -m pytest -q
```

## Core Endpoints

### Health

- GET /
- GET /health

### Suppliers

- POST /suppliers
- GET /suppliers
- GET /suppliers/{supplier_id}
- PUT /suppliers/{supplier_id}
- DELETE /suppliers/{supplier_id}

### Items

- POST /items
- POST /items/bulk
- GET /items
- PUT /items/{item_name}/{variant}
- DELETE /items/{item_name}/{variant}

### Usage Logs

- POST /usage-logs
- GET /usage-logs

### Analytics

- GET /alerts/low-stock
- GET /alerts/expiration-risk
- GET /analytics/burn-rate
- GET /analytics/reorder-suggestions

## Example Requests

Bulk item seed:

```bash
curl -X POST http://127.0.0.1:8000/items/bulk \
	-H "Content-Type: application/json" \
	-d @example/post_items_bulk.json
```

One usage log:

```bash
curl -X POST http://127.0.0.1:8000/usage-logs \
	-H "Content-Type: application/json" \
	-d '{"item_name":"Cup","item_variant":"12oz","quantity_used":40,"date":"2026-05-21"}'
```

Burn rate:

```bash
curl http://127.0.0.1:8000/analytics/burn-rate
```

Reorder suggestions:

```bash
curl http://127.0.0.1:8000/analytics/reorder-suggestions
```

Expiration risk alerts:

```bash
curl "http://127.0.0.1:8000/alerts/expiration-risk?days_ahead=14"
```

Supplier create:

```bash
curl -X POST http://127.0.0.1:8000/suppliers \
	-H "Content-Type: application/json" \
	-d '{"name":"Metro Food Supply","contact_name":"Ari Lee","lead_time_days":4}'
```

## Portfolio Notes

If you want a short resume bullet, this project can be described as:

- Built a FastAPI + SQLAlchemy inventory management API with CRUD, usage logging, low-stock alerts, burn-rate analytics, reorder suggestions, and perishable expiration-risk tracking.

## Notes

- Current persistence is SQLite for local development.
- The database file is intentionally ignored in git.
- For production, switch to PostgreSQL and environment-based configuration.

## Roadmap

- Add supplier and purchase order entities
- Add expiration-first usage recommendations for perishable items
- Add authentication and role-based access
- Add pagination and filtering for large inventories
- Add CI test workflow