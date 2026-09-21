# SmogCast – Design Document

## 1. Goal and Architecture

SmogCast is an application for monitoring and forecasting air quality in Poland.

The system uses:
- measurement data from GIOŚ,
- weather data from Open-Meteo,
- a local SQLite database,
- a machine learning model,
- FastAPI as the backend,
- Streamlit as the dashboard.

Main architecture:

    GIOŚ
      │
      ▼
    refresh_all.py
      │
      ▼
    SQLite
      │
      ├──────────────► FastAPI ──────────────► Streamlit
      │
      └──────────────► daily_measurements
                               │
                               ▼
                           ML model
                               │
                               ▼
                           forecast

Data refreshing has been separated from both the dashboard and the forecast process.

The dashboard and the forecast endpoint do not fetch new data directly from GIOŚ. They use data that has already been stored in the database.


## 2. Data Schema

### stations

Stores information about monitoring stations.

| Column | Type / role | Description |
|---|---|---|
| `id` | PK | unique station identifier |
| `name` |  | station name |
| `city` |  | city |
| `latitude` |  | latitude |
| `longitude` |  | longitude |

### sensors

Stores information about sensors assigned to stations.

| Column | Type / role | Description |
|---|---|---|
| `id` | PK | unique sensor identifier |
| `station_id` | FK | station identifier |
| `param_code` |  | parameter code, e.g. `PM10`, `PM2.5` |

One station may have multiple sensors, including more than one sensor measuring the same parameter.

Sensors are stored locally in the database, so they do not have to be fetched from the GIOŚ API during every refresh.

### measurements

Stores raw air quality measurements.

| Column | Type / role | Description |
|---|---|---|
| `id` | PK | measurement identifier |
| `sensor_id` | FK | sensor identifier |
| `timestamp` | UTC | measurement timestamp |
| `value` | nullable | concentration value in µg/m³ |

The following combination is unique:

`UNIQUE(sensor_id, timestamp)`

A `NULL` value means that there is no valid measurement and it is not automatically replaced with `0`.

### weather

Stores historical weather data for station locations.

| Column | Type / role | Description |
|---|---|---|
| `id` | PK | record identifier |
| `station_id` | FK | station identifier |
| `timestamp` |  | measurement timestamp |
| `temp_c` |  | temperature |
| `wind_ms` |  | wind speed |
| `humidity` |  | humidity |
| `pressure_hpa` |  | pressure |
| `precip_mm` |  | precipitation |

The model uses:
- temperature,
- wind speed,
- humidity.

The weather forecast for the next day is fetched from Open-Meteo.

### daily_measurements

Stores daily aggregates of PM10 and PM2.5 measurements.

| Column | Description |
|---|---|
| `station_id` | station identifier |
| `param_code` | parameter |
| `date` | date |
| `mean_value` | daily mean |
| `max_value` | daily maximum |
| `coverage` | data coverage |

The forecast uses the 7 most recent valid daily aggregates.

Records with `mean_value = NULL` are skipped.

### predictions

Table intended for storing generated forecasts.

| Column | Type / role | Description |
|---|---|---|
| `id` | PK | forecast identifier |
| `station_id` | FK | station identifier |
| `param_code` |  | forecasted parameter |
| `target_date` |  | forecast date |
| `predicted_value` |  | predicted concentration |
| `model_version` |  | model version |
| `created_at` |  | creation time |

Currently, forecasts are generated on demand and returned directly by the API.


## 3. Relationships Between Tables

    stations
       │
       ├──< sensors
       │      │
       │      └──< measurements
       │
       ├──< weather
       │
       ├──< daily_measurements
       │
       └──< predictions

Relationships:
- `stations.id -> sensors.station_id`
- `sensors.id -> measurements.sensor_id`
- `stations.id -> weather.station_id`
- `stations.id -> daily_measurements.station_id`
- `stations.id -> predictions.station_id`


## 4. Data Refresh

Data refreshing is handled by:

`scripts/refresh_all.py`

Refresh flow:

    list of stations from the database
            │
            ▼
    PM10 / PM2.5 sensors
            │
            ▼
       GIOŚ current
            │
            ▼
    comparison with the latest measurement
            │
       ┌────┴────┐
       │         │
    no gap     older gap
       │         │
       │         ▼
       │     GIOŚ archive
       │         │
       └────┬────┘
            ▼
      measurements
            │
            ▼
    daily_measurements

During a standard refresh, the current-data endpoint from GIOŚ is used.

The system fetches up to 100 records in a single request.

Only records newer than the latest valid measurement are saved to the database.

If the gap is older than the range available from the current-data endpoint, the archival endpoint is used.

HTTP connections use a shared `httpx.Client`, which allows connections to be reused.

After new data is saved, daily aggregates are recalculated for sensors that received new measurements.


## 5. Refresh Metrics

The updater records diagnostic information:
- number of HTTP requests,
- number of retries,
- number of current and archival requests,
- number of fetched records,
- number of new records,
- communication time with GIOŚ,
- database write time,
- aggregation time,
- total execution time.

Example measurement for 16 stations:

| Metric | Result |
|---|---:|
| Total time | 10.86 s |
| HTTP requests | 49 |
| Current-data requests | 43 |
| Archival requests | 6 |
| Fetched records | 1592 |
| New records | 6 |
| Current-data request time | 4.61 s |
| Archival request time | 3.13 s |
| Database write time | < 0.01 s |
| Aggregation time | 0.06 s |

The largest share of the total execution time is spent on communication with the GIOŚ API.


## 6. API

The dashboard communicates only with FastAPI.

### GET /stations

Returns stations available in the application.

### GET /stations/{station_id}/measurements

Returns measurement history for the selected parameter.

Supported parameters:
- `param`,
- `date_from`,
- `date_to`.

The dashboard fetches only the selected history range instead of the entire available history.

### GET /stations/{station_id}/latest

Returns the latest valid PM10 and PM2.5 measurements.

Records with `value = NULL` are skipped.

### GET /stations/{station_id}/forecast

Returns the PM10 and PM2.5 forecast for the next day.

This endpoint does not refresh data from GIOŚ.


## 7. Forecast

For each parameter, the system:

1. retrieves the latest valid measurement,
2. checks data freshness,
3. retrieves the 7 most recent valid daily aggregates,
4. retrieves the weather forecast for the next day,
5. builds input features,
6. performs the prediction,
7. checks the alarm threshold.

The model uses:
- PM value from the previous day,
- 3-day PM average,
- 7-day PM average,
- month,
- day of the week,
- weekend indicator,
- heating season indicator,
- temperature,
- wind speed,
- humidity.

PM10 and PM2.5 are forecast independently.

If `mean_value = NULL` appears in the daily aggregates, that record is skipped.

Seven valid daily values are required to generate a forecast.


## 8. Data Freshness

If the latest measurement is no more than 2 days old, the data receives the status:

`fresh`

If the data is older, it receives the status:

`stale`

The forecast can still be generated, but the user receives a warning that older data was used.


## 9. Model and Cache

The model is stored in:

`models/model_v2.joblib`

The model is kept in application memory so it does not have to be loaded again for every forecast request.

The system checks the modification time of the model file.

If the file changes after retraining, the new version is automatically loaded during the next forecast request.

If the file has not changed, the model is retrieved from cache.

This mechanism is covered by a test.


## 10. Dashboard

The Streamlit dashboard allows the user to:
- display a map of stations,
- switch between PM10 and PM2.5,
- select a station,
- view the latest measurements,
- view the forecast for the next day,
- view measurement history.

History can be displayed for:
- 7 days,
- 30 days,
- 90 days,
- 1 year.

Values are marked with colors:
- green – level below the threshold,
- yellow – value close to the threshold,
- red – threshold exceeded.

The dashboard also includes:
- a fixed header bar,
- the SmogCast logo,
- an application icon in the browser tab,
- information about data sources.

Data sources:
- GIOŚ – air quality data,
- Open-Meteo – weather data.

