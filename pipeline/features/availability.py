"""When each input is available, relative to the forecast issue date t (in whole days).

A feature for issue date t may only use input dates <= t - lag. These lags mirror real
operational latency (measured in Phase 0, docs/data_sources.md), so training sees exactly
the information the daily forecast will have. The leakage tests enforce them.
"""

CHL_LAG_DAYS = 2  # Copernicus OLCI NRT: newest day was 2026-11-15 on 2026-11-17
SST_LAG_DAYS = 1  # OSTIA NRT: newest day was 2026-11-17 on 2026-11-18
OCEAN_MODEL_LAG_DAYS = 1  # analysis for t-1; forecasts for t+1..t+7 come from the forecast run
WEATHER_LAG_DAYS = 1  # observed weather up to yesterday; t+1..t+7 from the weather forecast
