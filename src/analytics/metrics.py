def inventory_status(rows):
    return {"total": len(rows), "low_stock": sum(1 for r in rows if r[0] < r[1]), "stockout_rate": round(sum(1 for r in rows if r[0] <= 0) / max(len(rows), 1), 4)}

def supplier_kpis(rows):
    count = len(rows)
    return {"deliveries": count, "on_time_rate": round(sum(r[0] <= 0 for r in rows) / max(count, 1), 4), "fill_rate": round(sum(r[1] for r in rows) / max(sum(r[2] for r in rows), 1), 4)}
