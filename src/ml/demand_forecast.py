from sklearn.ensemble import RandomForestRegressor
from sklearn.pipeline import make_pipeline
from sklearn.impute import SimpleImputer

def train_forecaster(frame):
    features=["demand_lag_1","demand_lag_7","rolling_demand_7","day_of_week"]
    model=make_pipeline(SimpleImputer(),RandomForestRegressor(n_estimators=60,min_samples_leaf=2,random_state=42,n_jobs=1))
    model.fit(frame[features],frame.quantity)
    return model,features
