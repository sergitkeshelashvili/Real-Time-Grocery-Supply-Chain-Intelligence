from datetime import datetime
from uuid import uuid4

def detect(event):
    p = event["payload"]; result = []
    if event["event_type"] == "inventory" and p.get("quantity", 1e9) < p.get("safety_stock", 0):
        result.append(("stockout_risk", "high", "Inventory below safety stock"))
    if event["event_type"] == "demand_signals" and p.get("quantity", 0) > 55:
        result.append(("demand_spike", "medium", "Demand materially above expected level"))
    if event["event_type"] == "deliveries":
        if p.get("delivered_quantity", 0) / max(p.get("ordered_quantity", 1), .01) < .85: result.append(("fill_rate", "high", "Delivery fill rate below 85%"))
        if p.get("actual_delivery_time") and p.get("expected_delivery_time"):
            delay = datetime.fromisoformat(p["actual_delivery_time"]) - datetime.fromisoformat(p["expected_delivery_time"])
            if delay.total_seconds() > 12 * 3600: result.append(("supplier_delay", "high", "Delivery more than 12 hours late"))
    return result
