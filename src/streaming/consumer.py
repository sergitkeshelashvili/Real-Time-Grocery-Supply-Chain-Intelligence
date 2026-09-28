import json, time
from datetime import datetime
from uuid import UUID, uuid4
from confluent_kafka import Consumer
from pydantic import ValidationError
from src.common.config import KAFKA
from src.common.db import client
from src.common.logging import get_logger
from src.common.schemas import Event
from src.streaming.anomaly_rules import detect
from src.simulator.generators import PRODUCTS, STORES, SUPPLIERS

TOPICS = ["orders", "inventory", "deliveries", "prices", "demand_signals", "weather", "waste"]
def main():
    log = get_logger("stream-processor")
    ch = None
    while ch is None:
        try: ch = client()
        except Exception as exc: log.warning("ClickHouse unavailable: %s", exc); time.sleep(3)
    for table, records, key, columns, values in [
        ("dim_products", PRODUCTS, "product_id", ["product_id","product_name","category","subcategory","perishability","unit_price","supplier_id"], lambda p:[p["product_id"],p["product_name"],p["category"],p["category"],p["perishability"],p["unit_price"],p["supplier_id"]]),
        ("dim_stores", STORES, "store_id", ["store_id","store_name","city","region","latitude","longitude","store_type"], lambda s:[s["store_id"],s["store_name"],s["city"],s["region"],s["latitude"],s["longitude"],s["store_type"]]),
        ("dim_suppliers", SUPPLIERS, "supplier_id", ["supplier_id","supplier_name","country","reliability_score","lead_time_days"], lambda s:[s["supplier_id"],s["supplier_name"],s["country"],s["reliability_score"],s["lead_time_days"]]),
    ]:
        known={r[0] for r in ch.query(f"SELECT {key} FROM {table}").result_rows}
        missing=[values(record) for record in records if record[key] not in known]
        if missing: ch.insert(table,missing,column_names=columns)
    ch.command("CREATE TABLE IF NOT EXISTS fact_weather (event_id UUID, event_time DateTime64(3,'UTC'), city String, country String, latitude Float64, longitude Float64, temperature_c Nullable(Float64), feels_like_c Nullable(Float64), humidity_pct Nullable(UInt8), pressure_hpa Nullable(UInt16), wind_speed_mps Nullable(Float64), rain_1h_mm Float64, weather_main LowCardinality(String), description String, icon String, source LowCardinality(String)) ENGINE=MergeTree PARTITION BY toYYYYMM(event_time) ORDER BY (city,event_time)")
    ch.command("ALTER TABLE fact_demand ADD COLUMN IF NOT EXISTS requested_quantity Float64 DEFAULT 0")
    ch.command("ALTER TABLE fact_demand ADD COLUMN IF NOT EXISTS lost_sales_quantity Float64 DEFAULT 0")
    ch.command("ALTER TABLE fact_demand ADD COLUMN IF NOT EXISTS promotion UInt8 DEFAULT 0")
    ch.command("ALTER TABLE fact_inventory ADD COLUMN IF NOT EXISTS recommended_order_quantity Float64 DEFAULT 0")
    ch.command("ALTER TABLE fact_deliveries ADD COLUMN IF NOT EXISTS source LowCardinality(String) DEFAULT 'simulator'")
    ch.command("CREATE TABLE IF NOT EXISTS fact_waste (event_id UUID, event_time DateTime64(3,'UTC'), store_id String, product_id String, quantity Float64, unit_cost Float64, reason LowCardinality(String)) ENGINE=ReplacingMergeTree PARTITION BY toYYYYMM(event_time) ORDER BY (event_id)")
    ch.command("CREATE TABLE IF NOT EXISTS processed_event_ids (event_id UUID, processed_at DateTime DEFAULT now()) ENGINE=ReplacingMergeTree(processed_at) ORDER BY event_id")
    consumer = Consumer({"bootstrap.servers": KAFKA, "group.id": "grocery-processor-v1", "auto.offset.reset": "earliest", "enable.auto.commit": False})
    while True:
        try: consumer.subscribe(TOPICS); break
        except Exception: time.sleep(2)
    while True:
        msg = consumer.poll(1)
        if msg is None: continue
        if msg.error(): log.error("Kafka consumer error: %s", msg.error()); continue
        try:
            e = Event.model_validate_json(msg.value()); p = e.payload
            seen = ch.query("SELECT count() FROM processed_event_ids FINAL WHERE event_id=%(event_id)s", parameters={"event_id":e.event_id}).result_rows[0][0]
            if seen:
                consumer.commit(msg); continue
            dt = e.event_time.replace(tzinfo=None)
            row = [UUID(e.event_id), e.event_type, dt, e.source, p.get("store_id", p.get("city", "")), p.get("product_id", ""), p.get("supplier_id", ""), float(p.get("quantity", 0)), float(p.get("unit_price", 0)), p.get("expected_delivery_time"), p.get("actual_delivery_time"), json.dumps(p)]
            ch.insert("events", [row], column_names=["event_id","event_type","event_time","source","store_id","product_id","supplier_id","quantity","unit_price","expected_delivery_time","actual_delivery_time","payload"])
            t=e.event_type
            fact = {"orders":"fact_orders","inventory":"fact_inventory","deliveries":"fact_deliveries","prices":"fact_prices","demand_signals":"fact_demand","weather_observation":"fact_weather","waste":"fact_waste"}[t]
            cols, vals = None, None
            if t == "orders": cols,vals=["event_id","event_time","store_id","product_id","quantity","unit_price"],[UUID(e.event_id),dt,p.get("store_id",""),p.get("product_id",""),row[7],row[8]]
            if t == "demand_signals": cols,vals=["event_id","event_time","store_id","product_id","quantity","requested_quantity","lost_sales_quantity","promotion"],[UUID(e.event_id),dt,p.get("store_id",""),p.get("product_id",""),row[7],p.get("requested_quantity",row[7]),p.get("lost_sales_quantity",0),int(bool(p.get("promotion",False)))]
            elif t == "inventory": cols,vals=["event_id","event_time","store_id","product_id","quantity","reorder_point","safety_stock","recommended_order_quantity"],[UUID(e.event_id),dt,p.get("store_id",""),p.get("product_id",""),row[7],p.get("reorder_point",0),p.get("safety_stock",0),p.get("recommended_order_quantity",0)]
            elif t == "prices": cols,vals=["event_id","event_time","product_id","unit_price"],[UUID(e.event_id),dt,p.get("product_id",""),row[8]]
            elif t == "deliveries": cols,vals=["event_id","event_time","supplier_id","store_id","product_id","ordered_quantity","delivered_quantity","expected_delivery_time","actual_delivery_time","status","source"],[UUID(e.event_id),dt,p.get("supplier_id",""),p.get("store_id",""),p.get("product_id",""),p.get("ordered_quantity",0),p.get("delivered_quantity",0),p.get("expected_delivery_time"),p.get("actual_delivery_time"),p.get("status",""),e.source]
            elif t == "weather_observation": cols,vals=["event_id","event_time","city","country","latitude","longitude","temperature_c","feels_like_c","humidity_pct","pressure_hpa","wind_speed_mps","rain_1h_mm","weather_main","description","icon","source"],[UUID(e.event_id),dt,p["city"],p.get("country","DE"),p["latitude"],p["longitude"],p.get("temperature_c"),p.get("feels_like_c"),p.get("humidity_pct"),p.get("pressure_hpa"),p.get("wind_speed_mps"),p.get("rain_1h_mm",0),p.get("weather_main","Unknown"),p.get("description",""),p.get("icon",""),e.source]
            elif t == "waste": cols,vals=["event_id","event_time","store_id","product_id","quantity","unit_cost","reason"],[UUID(e.event_id),dt,p.get("store_id",""),p.get("product_id",""),p.get("quantity",0),p.get("unit_cost",0),p.get("reason","unknown")]
            ch.insert(fact,[vals],column_names=cols)
            for typ, severity, message in detect(e.model_dump(mode="json")):
                ch.insert("fact_supply_chain_alerts", [[uuid4(),dt,typ,severity,p.get("store_id",""),p.get("product_id",""),p.get("supplier_id",""),message]], column_names=["alert_id","event_time","alert_type","severity","store_id","product_id","supplier_id","message"])
            ch.insert("processed_event_ids", [[UUID(e.event_id)]], column_names=["event_id"])
            consumer.commit(msg); log.info("processed %s",t,extra={"event":"event_processed"})
        except (ValidationError, ValueError, KeyError, TypeError) as exc:
            log.error("Rejected malformed event: %s",exc); consumer.commit(msg)
        except Exception as exc:
            log.exception("Processing failed; Kafka offset left uncommitted: %s",exc); time.sleep(1)
if __name__ == "__main__": main()
