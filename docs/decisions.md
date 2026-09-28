# Design decisions and limits

- Python consumer instead of Spark: workload is intentionally small and demonstrates Kafka/ClickHouse fundamentals without a cluster-heavy stack.
- KRaft: fewer local services than ZooKeeper.
- MockAIProvider is the default and turns structured alerts into deterministic explanations. It adds no external dependency or credential requirement. Replace behind `AIProvider` only where generated prose is useful; deterministic rules own severity.
- This is a local portfolio prototype, not production-ready: one broker, plaintext local networking, no authentication, schema registry, durable DLQ, orchestration, CI/CD, model registry or feature store. Production needs clustered Kafka/ClickHouse, secret management, ACLs, monitoring, data contracts, deployment automation and tested idempotency.
