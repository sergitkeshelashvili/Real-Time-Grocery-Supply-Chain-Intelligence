import random
from datetime import datetime, timezone, timedelta
from src.common.schemas import Event


ON_HAND = {}

SUPPLIER_IDS = ["rheinlandDairy", "nrwFrische", "westfalenFleisch", "koelnBackhaus", "rheinGetraenke", "nordfrost", "ruhrtalFood", "hanseImport"]
PRODUCTS = [{"product_id": slug, "product_name": name, "category": category, "supplier_id": SUPPLIER_IDS[i % len(SUPPLIER_IDS)], "unit_price": price, "perishability": perish} for i, (slug, name, category, price, perish) in enumerate([
    ("wholeMilk_1l", "Whole Milk · 1 L", "Dairy", 1.29, 1), ("apples_Braeburn", "Braeburn Apples", "Produce", 2.49, 1), ("chickenBreast_500g", "Chicken Breast · 500 g", "Meat", 7.99, 1), ("sourdoughLoaf", "Sourdough Loaf", "Bakery", 3.20, 1), ("orangeJuice_1l", "Orange Juice · 1 L", "Beverages", 2.79, 0), ("frozenPeas_450g", "Frozen Peas · 450 g", "Frozen", 1.99, 0), ("pastaPenne_500g", "Penne Pasta · 500 g", "Pantry", 1.49, 0), ("yogurt_Natural", "Natural Yogurt", "Dairy", 0.89, 1), ("bananas_Fairtrade", "Fairtrade Bananas", "Produce", 1.69, 1), ("coffee_Beans", "Coffee Beans · 500 g", "Pantry", 5.49, 0)])]
CITIES = [("Düsseldorf", 51.23, 6.78, "duesseldorf"), ("Köln", 50.94, 6.96, "koeln"), ("Essen", 51.46, 7.01, "essen"), ("Dortmund", 51.51, 7.46, "dortmund"), ("Berlin", 52.52, 13.40, "berlinMitte"), ("Hamburg", 53.55, 9.99, "hamburg"), ("München", 48.14, 11.58, "muenchen"), ("Frankfurt am Main", 50.11, 8.68, "frankfurt")]
STORES = []
for city_index, (city, lat, lon, prefix) in enumerate(CITIES):
    for branch in range(1, 6):
        if prefix == "koeln":
            zone = "Nord" if branch <= 2 else "Sued" if branch <= 4 else "West"
            store_id = f"koeln{zone}{branch}"
        else:
            store_id = f"{prefix}{branch:02d}"
        STORES.append({"store_id": store_id, "store_name": f"Fresh Market {city} {branch}", "city": city, "region": "Germany", "latitude": lat, "longitude": lon, "store_type": "urban" if branch % 3 else "supermarket"})
SUPPLIERS = [{"supplier_id":sid,"supplier_name":name,"country":"Germany" if i<7 else "Netherlands","reliability_score":round(.88+i*.012,2),"lead_time_days":2+i%4} for i,(sid,name) in enumerate(zip(SUPPLIER_IDS,["Rheinland Dairy Cooperative","NRW Frischehandel","Westfalen Fleischwerk","Kölner Backhaus","Rhein Getränke Logistik","Nordfrost Foods","Ruhrtal Food Service","Hanse Import GmbH"]))]

LEGACY_PRODUCT_IDS = ["wholeMilk_1l", "apples_Braeburn", "chickenBreast_500g", "sourdoughLoaf", "orangeJuice_1l", "frozenPeas_450g", "pastaPenne_500g", "yogurt_Natural", "bananas_Fairtrade", "coffee_Beans"]
LEGACY_ID_MAP = {}
for old_index in range(1, 25):
    _, _, _, prefix = CITIES[(old_index - 1) % len(CITIES)]
    branch = (old_index - 1) // len(CITIES) + 1
    if prefix == "koeln":
        new_store_id = f"koeln{'Nord' if branch <= 2 else 'Sued'}{branch}"
    else:
        new_store_id = f"{prefix}{branch:02d}"
    LEGACY_ID_MAP[f"STORE_{old_index:02d}"] = new_store_id
for index, product_id in enumerate(LEGACY_PRODUCT_IDS):
    LEGACY_ID_MAP[f"PROD_{index:02d}"] = product_id
for index, supplier_id in enumerate(SUPPLIER_IDS, start=1):
    LEGACY_ID_MAP[f"SUP_{index:02d}"] = supplier_id

def readable_id(value):
    """Present IDs in old persisted demo facts using current catalog names."""
    return LEGACY_ID_MAP.get(value, value)

def generate_event(rng=random):
    store, product = rng.choice(STORES), rng.choice(PRODUCTS)
    typ = rng.choices(["orders", "inventory", "deliveries", "prices", "demand_signals", "waste"], [30, 24, 10, 3, 30, 3])[0]
    qty = max(1, rng.gauss(22, 8))
    now = datetime.now(timezone.utc)
    payload = {"store_id": store["store_id"], "product_id": product["product_id"], "supplier_id": product["supplier_id"]}
    key = (store["store_id"], product["product_id"])
    stock = ON_HAND.setdefault(key, rng.uniform(45, 110))
    # Retail demand peaks around lunch and after work, with a weekend uplift.
    hourly = {h: .35 for h in range(24)}
    for h, factor in {7:.65, 8:.9, 9:.8, 10:.75, 11:1.0, 12:1.35, 13:1.2, 14:.9, 15:.85, 16:1.05, 17:1.45, 18:1.6, 19:1.3, 20:.85}.items(): hourly[h] = factor
    promotion = rng.random() < .08
    demand_factor = hourly[now.hour] * (1.25 if now.weekday() >= 5 else 1.0) * (1.7 if promotion else 1.0)
    qty *= demand_factor
    if typ == "orders":
        payload.update(quantity=round(qty, 2), unit_price=product["unit_price"])
    elif typ == "demand_signals":
        requested = round(qty * (3 if rng.random() < .035 else 1), 2)
        sold = min(requested, stock)
        ON_HAND[key] = max(0, stock - sold)
        payload.update(quantity=round(sold, 2), requested_quantity=requested, lost_sales_quantity=round(requested-sold, 2), unit_price=product["unit_price"], promotion=promotion)
    elif typ == "inventory":
        reorder_point, safety_stock = 24, 12
        # Lead-time replenishment is imperfect and supplier reliability affects fill.
        if stock < reorder_point and rng.random() < .35:
            supplier = next(s for s in SUPPLIERS if s["supplier_id"] == product["supplier_id"])
            late = rng.random() > supplier["reliability_score"]
            ON_HAND[key] = stock + (rng.uniform(35, 60) if not late else rng.uniform(5, 18))
        payload.update(quantity=round(ON_HAND[key], 2), reorder_point=reorder_point, safety_stock=safety_stock, recommended_order_quantity=max(0, round(70-ON_HAND[key], 2)) if ON_HAND[key] < reorder_point else 0)
    elif typ == "deliveries":
        supplier = next(s for s in SUPPLIERS if s["supplier_id"] == product["supplier_id"])
        # Model a completed receipt after the supplier's nominal 2–5 day lead time.
        expected = now - timedelta(days=supplier["lead_time_days"])
        delayed = rng.random() > supplier["reliability_score"]
        actual = expected + timedelta(hours=rng.uniform(12, 36)) if delayed else expected - timedelta(hours=rng.uniform(0, 4))
        ordered = round(qty, 2)
        complete = rng.random() < min(.99, supplier["reliability_score"] + .04)
        delivered = ordered * (1.0 if complete else rng.uniform(.5, .8))
        payload.update(ordered_quantity=ordered, delivered_quantity=round(delivered, 2), expected_delivery_time=expected.isoformat(), actual_delivery_time=actual.isoformat(), status="delayed" if actual > expected + timedelta(hours=12) else "delivered")
        ON_HAND[key] = min(180, stock + delivered)
    elif typ == "waste":
        if product["perishability"]:
            wasted = round(min(stock, rng.uniform(.1, 2.5)), 2)
            payload.update(quantity=wasted, reason="expired", unit_cost=round(product["unit_price"]*.55, 2))
            ON_HAND[key] = max(0, stock-wasted)
        else:
            typ = "inventory"
            payload.update(quantity=round(stock, 2), reorder_point=24, safety_stock=12, recommended_order_quantity=max(0, round(70-stock, 2)) if stock < 24 else 0)
    else:
        payload["unit_price"] = round(product["unit_price"] * rng.uniform(.94, 1.06), 2)
    return typ, product["product_id"], Event(event_type=typ, source="simulator_v2", payload=payload).model_dump(mode="json")
