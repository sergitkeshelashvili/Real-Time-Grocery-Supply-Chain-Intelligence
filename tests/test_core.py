from datetime import datetime, timezone
from src.common.schemas import Event
from src.simulator.generators import generate_event, STORES, PRODUCTS, readable_id
from src.streaming.anomaly_rules import detect
from src.analytics.metrics import inventory_status, supplier_kpis
from src.ml.features import demand_features
from src.ai.prompt_analysis import _mock_answer
from src.simulator.weather import fetch_weather_events
import pandas as pd

def test_event_validation():
    e=Event(event_type="inventory",payload={"quantity":2})
    assert e.event_id and e.event_time.tzinfo

def test_generator_and_rules():
    typ,key,e=generate_event()
    assert typ in {"orders","inventory","deliveries","prices","demand_signals"} and key
    e={"event_type":"inventory","payload":{"quantity":1,"safety_stock":5}}
    assert detect(e)[0][0]=="stockout_risk"

def test_catalogs_use_readable_german_and_product_names():
    assert len(STORES)==40 and "koelnNord1" in {s["store_id"] for s in STORES}
    assert "essen05" in {s["store_id"] for s in STORES}
    assert "wholeMilk_1l" in {p["product_id"] for p in PRODUCTS}
    assert readable_id("STORE_01")=="duesseldorf01"
    assert readable_id("PROD_00")=="wholeMilk_1l"
    assert readable_id("SUP_01")=="rheinlandDairy"

def test_weather_provider_is_optional_without_key():
    assert fetch_weather_events(api_key="")==[]

def test_feature_pipeline_no_future_leakage():
    df=pd.DataFrame([{"product_id":"p","store_id":"s","day":f"2025-01-{i:02d}","quantity":i} for i in range(1,4)])
    result=demand_features(df)
    assert pd.isna(result.iloc[0].demand_lag_1) and result.iloc[1].demand_lag_1==1

def test_kpi_calculations():
    assert inventory_status([(2,5),(0,4)])=={"total":2,"low_stock":2,"stockout_rate":0.5}
    assert supplier_kpis([(0,8,10),(1,9,10)])=={"deliveries":2,"on_time_rate":0.5,"fill_rate":0.85}

def test_prompt_answer_uses_selected_live_context():
    context={"overview":{"events_processed":23},"supplier_performance":[],"demand_top_7d":[{"product_id":"p1","units_7d":42}],"low_inventory":[],"recent_alerts":[],"recent_forecasts":[]}
    answer=_mock_answer("What has the highest demand?",context)
    assert "p1" in answer and "42" in answer

def test_prompt_answer_handles_empty_metrics():
    context={"overview":{"events_processed":0},"supplier_performance":[],"demand_top_7d":[],"low_inventory":[],"recent_alerts":[],"recent_forecasts":[]}
    assert "not enough data" in _mock_answer("Show inventory",context)
