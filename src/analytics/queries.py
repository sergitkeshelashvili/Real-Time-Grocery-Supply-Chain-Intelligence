from src.common.db import client
from src.simulator.generators import readable_id

def query(sql): return client().query(sql).result_rows
def overview():
    n = query("SELECT uniqExact(event_id) FROM events")[0][0]
    orders = query("SELECT count() FROM fact_orders")[0][0]
    inventory = query("SELECT count(), countIf(quantity < safety_stock), countIf(quantity = 0) FROM fact_inventory")[0]
    alerts = query("SELECT count() FROM fact_supply_chain_alerts WHERE event_time > now() - INTERVAL 24 HOUR")[0][0]
    return {"events_processed": n, "orders": orders, "inventory_observations": inventory[0], "low_stock_observations": inventory[1], "active_alerts": alerts, "stockout_rate": round(inventory[2]/max(inventory[0],1),4)}
def alerts(limit=50):
    rows=query(f"SELECT toString(alert_id), event_time, alert_type, severity, store_id, product_id, supplier_id, message FROM fact_supply_chain_alerts ORDER BY event_time DESC LIMIT {int(limit)}")
    return [dict(zip(["alert_id","event_time","type","severity","store_id","product_id","supplier_id","message"],[r[0],r[1],r[2],r[3],readable_id(r[4]),readable_id(r[5]),readable_id(r[6]),r[7]])) for r in rows]
