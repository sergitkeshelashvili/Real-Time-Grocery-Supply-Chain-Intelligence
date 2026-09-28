CREATE TABLE IF NOT EXISTS grocery.fact_weather (
    event_id UUID,
    event_time DateTime64(3, 'UTC'),
    city String,
    country String,
    latitude Float64,
    longitude Float64,
    temperature_c Nullable(Float64),
    feels_like_c Nullable(Float64),
    humidity_pct Nullable(UInt8),
    pressure_hpa Nullable(UInt16),
    wind_speed_mps Nullable(Float64),
    rain_1h_mm Float64,
    weather_main LowCardinality(String),
    description String,
    icon String,
    source LowCardinality(String)
) ENGINE = MergeTree
PARTITION BY toYYYYMM(event_time)
ORDER BY (city, event_time);
