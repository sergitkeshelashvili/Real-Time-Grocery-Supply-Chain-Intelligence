# ML approach

The feature module implements leakage-aware lag-1, lag-7 and rolling-7 demand features; a scikit-learn RandomForest regressor is available as the supervised baseline. The periodic worker tolerates short histories by using a seven-observation rolling mean and scores demand with IsolationForest once at least eight observations exist. It persists output rows into `model_outputs`. Sparse local startup data is not enough to claim forecasting accuracy; evaluate with a chronological holdout and MAPE/MAE before operational use.
