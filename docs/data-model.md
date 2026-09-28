# ClickHouse model

`events` is the raw envelope landing table, partitioned monthly by event time and sorted by event type/time/id for replay and time-window scans. Typed facts are separated by business grain and sorted for common store/product/supplier time series. Monthly partitions limit part counts and support retention management. Dimensions are small ReplacingMergeTree lookup tables. `model_outputs` stores timestamped forecast/anomaly results. Alert facts support severity/time triage.

Catalogs populate the static dimensions at processor startup. Store identifiers are readable German location slugs (for example `koelnNord1`, `essen05`); product and supplier identifiers use stable names. `fact_weather` stores observed city-level current conditions separately, preserving provider and event timestamps. A production evolution would publish versioned dimensions and enrich facts through controlled reference-data updates.


`fact_demand` also records requested quantity, fulfilled quantity, lost sales, and promotion flag. `fact_waste` tracks synthetic expiry losses and estimated cost. Operations KPIs expose current observed availability, seven-day service level/lost sales/waste/OTIF, and a seasonal-naive same-weekday forecast backtest. These are demonstration estimates based on synthetic events; replace them with POS, inventory, purchase-order, and expiry data before treating them as operational truth.


Synthetic replenishment recommendations currently target 70 units of on-hand stock and should be tuned from actual shelf capacity, supplier lead time, minimum order quantities, and service-level goals. OTIF is marked warming up until at least 30 eligible delivery observations are available.
