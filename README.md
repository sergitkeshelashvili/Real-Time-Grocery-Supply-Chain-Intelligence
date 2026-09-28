# Real-Time Grocery Supply Chain Intelligence

A local data engineering portfolio prototype that simulates grocery operations, streams typed events through Kafka, writes raw and analytical facts to ClickHouse, runs demand/anomaly analysis, and serves KPIs and explainable alerts through FastAPI.

## Architecture

```text
  ┌─────────────┐    ┌──────────────────┐
  │ Weather API │───▶│ Event Simulator  │
  └─────────────┘    └────────┬─────────┘
                              ▼
                        ┌───────────┐
                        │   Kafka   │
                        └─────┬─────┘
                              ▼
                    ┌──────────────────┐
                    │ Stream Processor │
                    └────────┬─────────┘
                             ▼
                     ┌──────────────┐
                     │  ClickHouse  │
                     └──────┬───────┘
                       ┌────┴────┐
                       ▼         ▼
                      ML     Gemini AI
                       └────┬────┘
                            ▼
                       ┌──────────┐
                       │ FastAPI  │ → dashboard
                       └──────────┘
```

The data path is Simulator → Kafka → Python stream processor → ClickHouse → ML/API/dashboard. The dashboard polls live API aggregates every 15 seconds and includes a prompt-driven analyst: user questions are answered from bounded, read-only ClickHouse context rather than translated into executable SQL. Current OpenWeather conditions are collected for eight German cities every 15 minutes and kept distinct from synthetic event data. Current identifiers use readable catalog names such as `koelnNord1`, `essen05`, `wholeMilk_1l`, and `rheinlandDairy`; older persisted IDs are translated to these labels at the API layer. Stack: Python 3.12, Kafka KRaft, ClickHouse, FastAPI, Pydantic, pandas, NumPy, scikit-learn, Docker Compose.

## Run

```bash
cp .env.example .env  # optional; defaults work without a .env file
docker compose up --build

```
> **⚠️ AI Setup Reminder:** To enable synthesis from Gemini AI via the `/analyze` endpoint, ensure `AI_PROVIDER=gemini` and `GEMINI_API_KEY` are set in your `.env` file before running `docker compose up --build`. The local `.env` is git-ignored; never commit provider keys.
```

Open dashboard at [http://localhost:8000](http://localhost:8000), Swagger at [http://localhost:8000/docs](http://localhost:8000/docs), Kafka UI at [http://localhost:8081](http://localhost:8081), and ClickHouse HTTP at port 8123. No local Python, manual topic creation, or database setup is needed. For a fresh reset use `docker compose down -v` (removes local data).

## Topics and storage

Kafka topics: `orders`, `inventory`, `deliveries`, `prices`, `demand_signals`. ClickHouse tables: `events`, `dim_products`, `dim_stores`, `dim_suppliers`, `fact_orders`, `fact_inventory`, `fact_deliveries`, `fact_prices`, `fact_demand`, `fact_supply_chain_alerts`, `model_outputs`. Monthly partitioning and event-time sorting support time-series access. See [docs/architecture.md](docs/architecture.md), [docs/kafka-topics.md](docs/kafka-topics.md), and [docs/data-model.md](docs/data-model.md).

## API examples

`GET /health`, `/metrics/overview`, `/metrics/inventory`, `/metrics/demand`, `/metrics/suppliers`, `/alerts`, `/intelligence`, `/stores/{store_id}/inventory`, `/products/{product_id}/demand`, `/products/{product_id}/forecast`, `/suppliers/{supplier_id}/performance`.

Prompt-driven analysis uses `POST /analyze` with JSON:

```bash
curl -X POST http://localhost:8000/analyze \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"Which suppliers have the highest delay rate, and what should we do?"}'
```

`AI_PROVIDER=gemini` works with Google Gemini. To enable synthesis from Gemini AI, set `AI_PROVIDER=gemini`, add `GEMINI_API_KEY` in `.env`. Then rebuild with `docker compose up --build`. The model receives only bounded analytical results and has no SQL execution tool. Questions are limited to 2,000 characters. The local `.env` is git-ignored; never commit provider keys.

To enable current weather ingestion, set `OPENWEATHER_API_KEY` in `.env`; the simulator queries OpenWeather by the coordinates in the German city catalog, uses Celsius (`units=metric`), and publishes `weather` Kafka events into `fact_weather`. `GET /metrics/weather` shows observed city conditions with source and observation time. `WEATHER_POLL_SECONDS` controls refresh cadence (minimum 300 seconds). Weather API unavailability does not stop synthetic event generation. OpenWeather's terms/data freshness and account limits apply.

```bash
curl http://localhost:8000/metrics/overview
curl http://localhost:8000/intelligence
```

## ML and AI

Lag/rolling feature functions and a RandomForestRegressor baseline are reusable; the scheduled worker uses a rolling demand baseline plus IsolationForest anomaly scores and persists results. Gemini AI converts structured rule alerts into explanations and actions; prompt analysis can use live ClickHouse context with Gemini AI. See [docs/ml.md](docs/ml.md).

## Tests and maintenance

```bash
docker compose exec api pytest
# or locally with a Python 3.12 environment and requirements/dev.txt
pytest
```

`make up|down|logs|test|lint|format|clean` provides shortcuts. Dashboard screenshot placeholder: capture `/` after startup for a portfolio image.

## Limitations and production evolution

This is a local prototype: single broker, plaintext dev networking, simulator catalogs, basic rules, and small-data model baselines. Fact inserts are at-least-once and may duplicate after a crash. Store/product identifiers are now human-readable (for example `koelnNord1`, `essen05`, `wholeMilk_1l`); older persisted demo rows may retain their original IDs. Production requires broker clustering, explicit topic provisioning, schema registry/data contracts, deduplicating sink semantics, secrets management, TLS/ACLs, orchestration, monitoring, CI/CD, model registry, feature store, access control, and cloud deployment. Do not interpret demo anomaly scores as calibrated business risk.
