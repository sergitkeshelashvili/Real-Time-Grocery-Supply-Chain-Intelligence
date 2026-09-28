# Kafka topic strategy

Topics: `orders`, `inventory`, `deliveries`, `prices`, `demand_signals`, `weather`. Every message is a validated JSON Event envelope (`event_id`, `event_type`, `event_time`, `source`, `payload`). Key selection prioritizes partition-local ordering: product key for orders/prices/demand, store+product for inventory, supplier for delivery, and city for weather. Weather source is `openweathermap`; synthetic source is `simulator`. The local broker auto-creates topics; use explicit replication/partition counts and a schema registry outside local development.
