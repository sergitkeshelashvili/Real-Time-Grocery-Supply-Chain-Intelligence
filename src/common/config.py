import os

KAFKA = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:29092")
CH_HOST = os.getenv("CLICKHOUSE_HOST", "localhost")
CH_PORT = int(os.getenv("CLICKHOUSE_PORT", "8123"))
CH_DB = os.getenv("CLICKHOUSE_DATABASE", "grocery")
CH_USER = os.getenv("CLICKHOUSE_USER", "grocery")
CH_PASSWORD = os.getenv("CLICKHOUSE_PASSWORD", "grocery_local")

