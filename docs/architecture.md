# Architecture

The local prototype runs Kafka in single-node KRaft mode. Simulator events are JSON envelopes keyed by entity identity, then consumed by a Python consumer that validates, writes raw and typed records to ClickHouse, and emits deterministic rule alerts. The API reads ClickHouse directly; the periodic ML worker persists product/store demand baselines and Isolation Forest scores.

The simulator also polls OpenWeather's current-weather endpoint by the fixed latitude/longitude coordinates for each catalog city in metric units, then publishes `weather` events. This avoids the deprecated city-name lookup and keeps one low-rate snapshot per city (15-minute default interval). Weather is a separate external observation, not fabricated demand: the dashboard and prompt context mark it as OpenWeather data. If the key is absent or the provider is unavailable, synthetic event processing continues.

Prompt requests enter `POST /analyze`. The API takes user text and gathers bounded, read-only approved queries (overview, low stock, seven-day demand, supplier delivery performance, recent alerts and forecast outputs). It never converts user text into SQL. An OpenAI-compatible provider can synthesize this context when configured; the credential-free default mock selects relevant facts and applies simple action rules.

```text
Simulator → Kafka topics → Python stream processor → ClickHouse facts/events
                                                    ↘ alert rules
ClickHouse → ML worker → forecasts/scores → FastAPI + Mock AI → dashboard
```

Kafka auto-creates topics for this local demo. Deployments should provision them explicitly. The simulator uses a seeded RNG for reproducibility, though event timestamps naturally vary. The consumer commits offsets after writes; ClickHouse inserts are at-least-once and raw records use ReplacingMergeTree with event_id. Typed fact retries can duplicate rows, so production should deduplicate using a durable ingestion key.

Partition keys: orders/demand/prices use product_id; inventory uses store_id:product_id; deliveries use supplier_id. This preserves per-entity ordering while spreading traffic.


The simulator now varies demand by hour, weekend, and promotion; sales draw down process-local stock, inventory observations can trigger lead-time replenishment, supplier delivery outcomes depend on catalog reliability, and perishable products can generate expiry waste. These remain synthetic scenarios, not retailer observations. `fact_demand` records requested, fulfilled, lost-sales units and promotion flags; `fact_waste` records waste quantity and estimated cost. A processed-event ledger reduces duplicate writes during Kafka replay, while the consumer still has a small crash window between fact writes and ledger insert; production should use a transactional/idempotent sink pattern.
