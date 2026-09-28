import numpy as np
from sklearn.ensemble import IsolationForest

def anomaly_scores(values):
    x=np.asarray(values,dtype=float).reshape(-1,1)
    if len(x)<8: return np.zeros(len(x))
    model=IsolationForest(contamination="auto",random_state=42).fit(x)
    return -model.score_samples(x)
