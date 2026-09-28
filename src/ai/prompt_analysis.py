"""Prompt-to-insight flow backed by approved, read-only ClickHouse queries."""
import json
import os
from datetime import datetime, timezone

from src.common.db import client
from src.simulator.generators import readable_id


def collect_context(db=None):
    """Gather bounded, structured facts; user text is never turned into SQL."""
    db = db or client()

    def rows(sql):
        return db.query(sql).result_rows

    inventory = rows(
        "SELECT store_id, product_id, argMax(quantity,event_time), "
        "argMax(safety_stock,event_time), argMax(recommended_order_quantity,event_time), "
        "argMax(reorder_point,event_time) FROM fact_inventory "
        "WHERE event_time > now()-INTERVAL 7 DAY "
        "GROUP BY store_id,product_id HAVING argMax(quantity,event_time) < "
        "argMax(reorder_point,event_time) ORDER BY 3 ASC LIMIT 15"
    )
    demand = rows(
        "SELECT product_id, round(sum(quantity),2) AS units FROM fact_demand "
        "WHERE event_time > now()-INTERVAL 7 DAY GROUP BY product_id "
        "ORDER BY units DESC LIMIT 10"
    )
    suppliers = rows(
        "SELECT supplier_id, count(), round(avg(delivered_quantity/"
        "nullIf(ordered_quantity,0)),3), round(countIf(status='delayed')/count(),3) "
        "FROM fact_deliveries GROUP BY supplier_id ORDER BY 4 DESC LIMIT 10"
    )
    recent_alerts = rows(
        "SELECT toString(alert_id), alert_type, severity, store_id, product_id, "
        "supplier_id, message, toString(event_time) FROM fact_supply_chain_alerts "
        "ORDER BY event_time DESC LIMIT 20"
    )
    forecasts = rows(
        "SELECT product_id, store_id, predicted_demand, anomaly_score, "
        "toString(event_time) FROM model_outputs ORDER BY event_time DESC LIMIT 10"
    )
    weather = rows(
        "SELECT multiIf(city='München','Munich', city='Frankfurt am Main','Frankfurt', city='Köln','Cologne', city) AS norm_city, "
        "argMax(temperature_c,event_time), argMax(humidity_pct,event_time), "
        "argMax(wind_speed_mps,event_time), argMax(rain_1h_mm,event_time), "
        "argMax(weather_main,event_time), argMax(description,event_time), "
        "toString(max(event_time)) FROM fact_weather GROUP BY norm_city ORDER BY norm_city LIMIT 20"
    )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "overview": {
            "events_processed": rows("SELECT count() FROM events")[0][0],
            "orders": rows("SELECT count() FROM fact_orders")[0][0],
            "active_alerts_24h": rows("SELECT count() FROM fact_supply_chain_alerts WHERE event_time > now()-INTERVAL 24 HOUR")[0][0],
        },
        "operational_kpis_7d": {
            "requested_units": rows("SELECT sumIf(requested_quantity,requested_quantity>0)+sumIf(quantity,requested_quantity=0) FROM fact_demand WHERE event_time > now()-INTERVAL 7 DAY")[0][0],
            "fulfilled_units": rows("SELECT sum(quantity) FROM fact_demand WHERE event_time > now()-INTERVAL 7 DAY")[0][0],
            "lost_sales_units": rows("SELECT sum(lost_sales_quantity) FROM fact_demand WHERE event_time > now()-INTERVAL 7 DAY")[0][0],
            "waste_units": rows("SELECT sum(quantity) FROM fact_waste FINAL WHERE event_time > now()-INTERVAL 7 DAY")[0][0],
            "waste_cost_eur": rows("SELECT sum(quantity*unit_cost) FROM fact_waste FINAL WHERE event_time > now()-INTERVAL 7 DAY")[0][0],
            "otif_rate": rows("SELECT countIf(actual_delivery_time <= expected_delivery_time AND delivered_quantity >= ordered_quantity)/greatest(count(),1) FROM fact_deliveries WHERE actual_delivery_time IS NOT NULL AND source='simulator_v2' AND event_time > now()-INTERVAL 7 DAY")[0][0],
            "otif_observations": rows("SELECT count() FROM fact_deliveries WHERE actual_delivery_time IS NOT NULL AND source='simulator_v2' AND event_time > now()-INTERVAL 7 DAY")[0][0],
        },
        "low_inventory": [dict(zip(["store_id", "product_id", "quantity", "safety_stock", "recommended_order_quantity"], [readable_id(r[0]),readable_id(r[1]),r[2],r[3],max(float(r[4] or 0),round(max(0,70-float(r[2])),2)) if float(r[2]) < r[5] else 0])) for r in inventory],
        "demand_top_7d": [dict(zip(["product_id", "units_7d"], [readable_id(r[0]),r[1]])) for r in demand],
        "supplier_performance": [dict(zip(["supplier_id", "deliveries", "fill_rate", "delay_rate"], [readable_id(r[0]),r[1],r[2],r[3]])) for r in suppliers],
        "recent_alerts": [dict(zip(["alert_id", "type", "severity", "store_id", "product_id", "supplier_id", "message", "event_time"], [r[0],r[1],r[2],readable_id(r[3]),readable_id(r[4]),readable_id(r[5]),r[6],r[7]])) for r in recent_alerts],
        "recent_forecasts": [dict(zip(["product_id", "store_id", "predicted_demand", "anomaly_score", "generated_at"], [readable_id(r[0]),readable_id(r[1]),r[2],r[3],r[4]])) for r in forecasts],
        "weather_by_city": [dict(zip(["city", "temperature_c", "humidity_pct", "wind_speed_mps", "rain_1h_mm", "condition", "description", "observed_at"], r)) for r in weather],
    }


def _mock_answer(prompt, context):
    q = prompt.lower()
    sections = []
    if any(w in q for w in ("supplier", "სუპლაიერ", "მომწოდებელ", "მომწოდებლ")):
        suppliers = context["supplier_performance"][:5]
        text = [f"{s['supplier_id']}: delay rate {s['delay_rate']:.1%}, fill rate {s['fill_rate']:.1%} across {s['deliveries']} deliveries." for s in suppliers]
        if suppliers and any(s["delay_rate"] > .1 for s in suppliers):
            worst = suppliers[0]
            text.append(f"Recommended action: review the delivery plan with {worst['supplier_id']} and increase replenishment coverage for affected products.")
        sections.append(("Supplier performance", text))
    if any(w in q for w in ("demand", "დemand", "მოთხოვნ", "გაყიდვ")):
        sections.append(("Demand · last 7 days", [f"{r['product_id']}: {r['units_7d']} units" for r in context["demand_top_7d"][:5]]))
    if any(w in q for w in ("stock", "inventory", "მარაგ", "ინვენტარ")):
        low = context["low_inventory"][:8]
        sections.append(("Low inventory", [f"{r['store_id']} / {r['product_id']}: {r['quantity']} units remain (safety stock {r['safety_stock']}); suggested order {r['recommended_order_quantity']} units." for r in low]))
        if low: sections[-1][1].append("Recommended action: prioritize replenishment for these store/product pairs.")
    if any(w in q for w in ("otif", "waste", "service level", "lost sales", "expiry")):
        k = context["operational_kpis_7d"]
        requested = float(k["requested_units"] or 0); fulfilled = float(k["fulfilled_units"] or 0)
        sections.append(("Operations KPIs · last 7 days", [
            f"Service level: {fulfilled/max(requested,1):.1%} ({fulfilled:.1f} fulfilled of {requested:.1f} requested units).",
            f"Lost sales: {float(k['lost_sales_units'] or 0):.1f} units; recorded waste: {float(k['waste_units'] or 0):.1f} units (€{float(k['waste_cost_eur'] or 0):.2f} estimated cost).",
            f"Supplier OTIF: {float(k['otif_rate'] or 0):.1%} across {int(k['otif_observations'] or 0)} eligible deliveries (warming up below 30 observations)."
        ]))
    if any(w in q for w in ("forecast", "პროგნოზ", "forecast accuracy", "wape")):
        sections.append(("Recent forecasts", [f"{r['product_id']} at {r['store_id']}: predicted demand {r['predicted_demand']:.1f}; anomaly score {r['anomaly_score']:.3f}." for r in context["recent_forecasts"][:5]]))
    if any(w in q for w in ("weather", "rain", "temperature", "weather", "ამინ", "წვიმ", "ტემპერატურ")):
        sections.append(("Live weather · OpenWeather", [f"{r['city']}: {r['temperature_c']}°C, {r['condition']} ({r['description']}), humidity {r['humidity_pct']}%, wind {r['wind_speed_mps']} m/s, rain {r['rain_1h_mm']} mm/h." for r in context["weather_by_city"]]))
    if any(w in q for w in ("alert", "risk", "ანომალ", "რისკ", "გაფრთხილ")):
        sections.append(("Recent alerts", [f"{r['severity'].upper()} {r['type']} · {r['store_id']} / {r['product_id']}: {r['message']}" for r in context["recent_alerts"][:8]]))
    if not sections:
        sections.append(("Current overview", [f"{context['overview']['events_processed']} events processed; {context['overview']['orders']} orders; {context['overview']['active_alerts_24h']} alerts in the last 24 hours."]))
        sections.append(("Recent alerts", [f"{r['severity'].upper()} {r['type']} · {r['store_id']} / {r['product_id']}: {r['message']}" for r in context["recent_alerts"][:5]]))
    has_observations = any(data for _, data in sections if _ != "Current overview")
    if not has_observations:
        return "There is not enough data yet to answer this reliably. Let the simulator run longer, then retry. " + f"Events observed: {context['overview']['events_processed']}."
    return "\n\n".join(f"{title}:\n" + ("\n".join(f"• {item}" for item in data) if isinstance(data, list) else str(data)) for title, data in sections)


def analyze_prompt(prompt: str):
    context = collect_context()
    provider = os.getenv("AI_PROVIDER", "mock").strip().lower()
    if provider == "mock":
        answer = _mock_answer(prompt, context)
        provider_name = "mock"
    elif provider in {"openai", "groq", "google"}:
        if provider == "google":
            from google import genai
            from google.genai import types
            api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("AI_API_KEY")
            if not api_key:
                raise ValueError("AI_PROVIDER=google but no GOOGLE_API_KEY is configured")
            model = os.getenv("AI_MODEL") or "gemini-3.8-flash"
            try:
                client = genai.Client(api_key=api_key)
                response = client.models.generate_content(
                    model=model,
                    contents=f"Question:\n{prompt}\n\nVerified ClickHouse context (JSON):\n{json.dumps(context, ensure_ascii=False, default=str)}",
                    config=types.GenerateContentConfig(
                        system_instruction="You are a grocery supply-chain analyst. Answer in the language of the user's prompt. Use only the supplied structured facts. Say when data is insufficient. Separate measured facts from recommendations. Never claim to have executed arbitrary SQL or invent values.",
                        temperature=0.2,
                    )
                )
                answer = response.text or "The model returned an empty answer."
            except Exception as exc:
                raise RuntimeError(f"Google API request failed ({type(exc).__name__}): {exc}") from None
        else:
            from openai import OpenAI
            api_key = os.getenv("AI_API_KEY") or (os.getenv("GROQ_API_KEY") if provider == "groq" else None) or (os.getenv("OPENAI_API_KEY") if provider == "openai" else None)
            if not api_key:
                raise ValueError(f"AI_PROVIDER={provider} but no API key is configured")
            base_url = os.getenv("AI_BASE_URL") or ("https://api.groq.com/openai/v1" if provider == "groq" else None)
            model = os.getenv("AI_MODEL") or ("llama-3.1-8b-instant" if provider == "groq" else "gpt-4o-mini")
            llm = OpenAI(api_key=api_key, base_url=base_url, timeout=30, max_retries=1)
            try:
                response = llm.chat.completions.create(
                    model=model,
                    temperature=0.2,
                    messages=[
                        {"role": "system", "content": "You are a grocery supply-chain analyst. Answer in the language of the user's prompt. Use only the supplied structured facts. Say when data is insufficient. Separate measured facts from recommendations. Never claim to have executed arbitrary SQL or invent values."},
                        {"role": "user", "content": f"Question:\n{prompt}\n\nVerified ClickHouse context (JSON):\n{json.dumps(context, ensure_ascii=False, default=str)}"},
                    ],
                )
            except Exception as exc:
                status = getattr(exc, "status_code", None)
                error = {}
                try: error = (exc.response.json() or {}).get("error", {})
                except Exception: pass
                code = str(error.get("code") or "").lower()
                kind = str(error.get("type") or "").lower()
                message = str(error.get("message") or "").lower()
                if status == 429 and (code in {"insufficient_quota", "credit_balance_exhausted"} or kind == "insufficient_quota" or "quota" in message):
                    raise ValueError(f"{provider.title()} API credit balance is exhausted. Add API credits or set AI_PROVIDER=mock in .env.") from None
                if status == 429:
                    raise ValueError(f"{provider.title()} API rate limit reached. Wait briefly and retry.") from None
                raise RuntimeError(f"{provider.title()} request failed ({type(exc).__name__}). Check model access and API configuration.") from None
            answer = response.choices[0].message.content or "The model returned an empty answer."
        provider_name = provider
    else:
        raise ValueError("AI_PROVIDER must be mock, openai, groq, or google")
    return {"prompt": prompt, "answer": answer, "generated_at": context["generated_at"], "provider": provider_name, "data_context": context}
