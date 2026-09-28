import time
from datetime import datetime, timezone
from src.common.db import client
from src.common.logging import get_logger
from src.ml.anomaly_detection import anomaly_scores

def run_once(ch):
    rows=ch.query("SELECT product_id, store_id, toDate(event_time) day, sum(quantity) quantity FROM fact_demand WHERE event_time > now() - INTERVAL 30 DAY GROUP BY product_id,store_id,day ORDER BY product_id,store_id,day").result_rows
    if not rows:return 0
    by_series={}
    for product,store,day,qty in rows: by_series.setdefault((product,store),[]).append(float(qty))
    now=datetime.now(timezone.utc).replace(tzinfo=None); output=[]
    for (product,store),values in by_series.items():
        recent=values[-7:]; forecast=sum(recent)/len(recent) if recent else 0
        scores=anomaly_scores(values); score=float(scores[-1]) if len(scores) else 0
        output.append([now,store,product,forecast,score,"isolation_forest+rolling_baseline"])
    ch.insert("model_outputs",output,column_names=["event_time","store_id","product_id","predicted_demand","anomaly_score","model"])
    return len(output)
def main():
    log=get_logger("ml-service")
    while True:
        try:
            count=run_once(client()); log.info("model records: %s",count,extra={"event":"model_run"})
        except Exception as exc: log.warning("ML pass deferred: %s",exc)
        time.sleep(60)
if __name__=="__main__":main()
