import pandas as pd

def demand_features(frame):
    """Sort by series/day and build strictly historical lag and rolling features."""
    df=frame.sort_values(["product_id","store_id","day"]).copy()
    group=df.groupby(["product_id","store_id"], observed=True)["quantity"]
    df["demand_lag_1"]=group.shift(1); df["demand_lag_7"]=group.shift(7)
    df["rolling_demand_7"]=group.transform(lambda s:s.shift(1).rolling(7,min_periods=1).mean())
    df["day_of_week"]=pd.to_datetime(df["day"]).dt.dayofweek
    return df
