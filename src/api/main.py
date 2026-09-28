from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from datetime import datetime, timedelta, timezone
from src.analytics.queries import overview, alerts, query
from src.ai.intelligence import explain
from src.ai.prompt_analysis import analyze_prompt
from src.api.models import PromptRequest
from src.simulator.generators import readable_id

app=FastAPI(title="Real-Time Grocery Supply Chain Intelligence", version="1.0.0")
@app.post("/analyze")
def analyze(request: PromptRequest):
    prompt=request.prompt.strip()
    if not prompt: raise HTTPException(400,"Prompt cannot be empty")
    if len(prompt)>2000: raise HTTPException(413,"Prompt must be 2,000 characters or fewer")
    try: return analyze_prompt(prompt)
    except ValueError as exc: raise HTTPException(503,str(exc))
    except Exception as exc: raise HTTPException(502,f"Prompt analysis failed: {str(exc)}")
@app.get("/health")
def health():
    try: query("SELECT 1"); return {"status":"ok"}
    except Exception as exc: raise HTTPException(503,str(exc))
@app.get("/metrics/overview")
def metrics_overview(): return overview()
@app.get("/metrics/inventory")
def inventory():
    rows=query("SELECT argMax(quantity,event_time), argMax(safety_stock,event_time), store_id, product_id, argMax(recommended_order_quantity,event_time), argMax(reorder_point,event_time) FROM fact_inventory WHERE event_time > now()-INTERVAL 7 DAY GROUP BY store_id,product_id ORDER BY store_id,product_id LIMIT 500")
    return [{"quantity":r[0],"safety_stock":r[1],"store_id":readable_id(r[2]),"product_id":readable_id(r[3]),"reorder_point":r[5],"low_stock":r[0]<r[5],"recommended_order_quantity":max(float(r[4] or 0), round(max(0,70-float(r[0])),2)) if float(r[0]) < r[5] else 0} for r in rows]
@app.get("/metrics/realism")
def realism_metrics():
    inv = query("SELECT store_id,product_id,argMax(quantity,event_time) FROM fact_inventory WHERE event_time > now()-INTERVAL 7 DAY GROUP BY store_id,product_id")
    availability = sum(1 for r in inv if r[2] > 0) / max(len(inv), 1)
    demand_rows = query("SELECT sumIf(requested_quantity,requested_quantity>0)+sumIf(quantity,requested_quantity=0),sum(quantity),sum(lost_sales_quantity) FROM fact_demand WHERE event_time > now()-INTERVAL 7 DAY")[0]
    waste = query("SELECT sum(quantity),sum(quantity*unit_cost) FROM fact_waste FINAL WHERE event_time > now()-INTERVAL 7 DAY")[0]
    deliveries = query("SELECT count(),countIf(actual_delivery_time <= expected_delivery_time AND delivered_quantity >= ordered_quantity),sum(ordered_quantity),sum(delivered_quantity) FROM fact_deliveries WHERE actual_delivery_time IS NOT NULL AND source='simulator_v2' AND event_time > now()-INTERVAL 7 DAY")[0]
    requested, fulfilled, lost = [float(x or 0) for x in demand_rows]
    return {"availability_rate": round(availability,4), "otif_observations": int(deliveries[0]), "otif_status": "warming_up" if deliveries[0] < 30 else "ready", "requested_units_7d": round(requested,2), "fulfilled_units_7d": round(fulfilled,2), "lost_sales_units_7d": round(lost,2), "service_level_7d": round(fulfilled/max(requested,1),4), "waste_units_7d": round(float(waste[0] or 0),2), "waste_cost_7d": round(float(waste[1] or 0),2), "otif_rate": round(deliveries[1]/max(deliveries[0],1),4), "delivery_fill_rate": round(deliveries[3]/max(deliveries[2],1),4)}

@app.get("/metrics/forecast-accuracy")
def forecast_accuracy():
    rows=query("SELECT product_id,store_id,toDate(event_time),sum(quantity) FROM fact_demand WHERE event_time > now()-INTERVAL 35 DAY GROUP BY product_id,store_id,toDate(event_time) ORDER BY product_id,store_id,toDate(event_time)")
    actual={(r[0],r[1],r[2]):float(r[3]) for r in rows}
    errors=[]; absolute=0.0; total=0.0
    for (product,store,day),value in actual.items():
        prior=actual.get((product,store,day-timedelta(days=7)))
        if prior is not None:
            errors.append(abs(value-prior)); absolute += abs(value-prior); total += value
    return {"method":"seasonal naive · same weekday last week", "comparisons":len(errors), "mae_units":round(sum(errors)/max(len(errors),1),2), "wape":round(absolute/max(total,1),4), "status":"ready" if errors else "warming_up"}

@app.get("/metrics/demand")
def demand(): return [{"day":str(r[0]),"product_id":readable_id(r[1]),"quantity":r[2]} for r in query("SELECT toDate(event_time),product_id,sum(quantity) FROM fact_demand WHERE event_time > now()-INTERVAL 7 DAY GROUP BY toDate(event_time),product_id ORDER BY 1,2 LIMIT 200")]
@app.get("/metrics/demand/trend")
def demand_trend():
    rows=query("SELECT toUnixTimestamp(toStartOfHour(event_time)),sum(quantity) FROM fact_demand WHERE event_time >= now()-INTERVAL 7 DAY GROUP BY toStartOfHour(event_time)")
    values={int(ts):float(total) for ts,total in rows}
    now=datetime.now(timezone.utc).replace(minute=0,second=0,microsecond=0)
    start=now-timedelta(hours=167)
    return [{"time":(start+timedelta(hours=i)).isoformat(),"quantity":values.get(int((start+timedelta(hours=i)).timestamp()),0)} for i in range(168)]
@app.get("/metrics/weather")
def weather():
    return [{"city":r[0],"temperature_c":r[1],"feels_like_c":r[2],"humidity_pct":r[3],"wind_speed_mps":r[4],"rain_1h_mm":r[5],"condition":r[6],"description":r[7],"icon":r[8],"observed_at":r[9],"source":"OpenWeather"} for r in query("SELECT multiIf(city='München','Munich', city='Frankfurt am Main','Frankfurt', city='Köln','Cologne', city) AS norm_city,argMax(temperature_c,event_time),argMax(feels_like_c,event_time),argMax(humidity_pct,event_time),argMax(wind_speed_mps,event_time),argMax(rain_1h_mm,event_time),argMax(weather_main,event_time),argMax(description,event_time),argMax(icon,event_time),max(event_time) FROM fact_weather GROUP BY norm_city ORDER BY norm_city")]
@app.get("/metrics/suppliers")
def suppliers(): return [{"supplier_id":readable_id(r[0]),"deliveries":r[1],"avg_fill_rate":r[2],"delay_rate":r[3]} for r in query("SELECT supplier_id,count(),avg(delivered_quantity/nullIf(ordered_quantity,0)),countIf(status='delayed')/count() FROM fact_deliveries GROUP BY supplier_id")]
@app.get("/alerts")
def get_alerts(limit:int=50): return alerts(max(1,min(limit,500)))
@app.get("/alerts/{alert_id}")
def alert_detail(alert_id:str):
    if not all(c in "0123456789abcdefABCDEF-" for c in alert_id): raise HTTPException(404,"Alert not found")
    rows=query(f"SELECT toString(alert_id),event_time,alert_type,severity,store_id,product_id,supplier_id,message FROM fact_supply_chain_alerts WHERE alert_id=toUUID('{alert_id}') LIMIT 1")
    if not rows: raise HTTPException(404,"Alert not found")
    values=rows[0]
    return dict(zip(["alert_id","event_time","type","severity","store_id","product_id","supplier_id","message"],[values[0],values[1],values[2],values[3],readable_id(values[4]),readable_id(values[5]),readable_id(values[6]),values[7]]))
@app.get("/stores/{store_id}/inventory")
def store_inventory(store_id:str): return [r for r in inventory() if r["store_id"]==store_id]
@app.get("/products/{product_id}/demand")
def product_demand(product_id:str): return [r for r in demand() if r["product_id"]==product_id]
@app.get("/products/{product_id}/forecast")
def forecast(product_id:str):
    rows=query("SELECT store_id,predicted_demand,anomaly_score,event_time FROM model_outputs WHERE product_id=%(id)s ORDER BY event_time DESC LIMIT 100")
    return [{"store_id":readable_id(r[0]),"predicted_demand":r[1],"anomaly_score":r[2],"generated_at":r[3]} for r in rows]
@app.get("/suppliers/{supplier_id}/performance")
def supplier_performance(supplier_id:str): return [r for r in suppliers() if r["supplier_id"]==supplier_id]
@app.get("/intelligence")
def intelligence():
    risks=[{"type":a["type"],"store":a["store_id"],"product":a["product_id"],"severity":a["severity"],"supplier":a["supplier_id"]} for a in alerts(20)]
    return {"generated_at":__import__("datetime").datetime.now(__import__("datetime").timezone.utc),"system_status":"critical" if any(r["severity"]=="high" for r in risks) else "warning" if risks else "healthy","top_risks":risks,"supplier_risks":[r for r in risks if r["type"]=="supplier_delay"],"demand_anomalies":[r for r in risks if r["type"]=="demand_spike"],"recommended_actions":explain(risks)}
@app.get("/",response_class=HTMLResponse)
def dashboard(): return Path("/app/dashboard/index.html").read_text()
app.mount("/static",StaticFiles(directory="/app/dashboard"),name="static")
