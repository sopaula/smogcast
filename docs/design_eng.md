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

Data refreshing has been separated from both the dashboard and the forecasting process.

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

The forecast uses:

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

`coverage` indicates how much of the day contains valid measurements.

For example:
- 24 valid measurements means `100%`,
- 12 valid measurements means `50%`,
- 6 valid measurements means `25%`.

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


## 4. Data Initialization and Refresh

### First Database Initialization

The first application startup uses:

`scripts/init_db.py`

The script performs the following steps:

1. creates the SQLite tables,
2. fetches and stores station and sensor metadata,
3. imports historical GIOŚ measurements,
4. imports historical Open-Meteo weather data,
5. creates daily aggregates.

First startup flow:

    empty database
        │
        ▼
    create_tables()
        │
        ▼
    metadata
        │
        ▼
    historical PM + weather
        │
        ▼
    daily_measurements
        │
        ▼
    database ready

After initialization, further updates are handled by:

`scripts/refresh_all.py`

### Standard Refresh

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

If an older gap in the data is detected, the archival endpoint is used.

HTTP connections use a shared `httpx.Client`, which allows connections to be reused.

After new data is saved, daily aggregates are recalculated for sensors that received new measurements.

Measurement upsert uses the following combination:

`(sensor_id, timestamp)`

If GIOŚ returns the same measurement again with a corrected value, the existing record is updated instead of creating a duplicate.

This mechanism is covered by a test.


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

### Standard Run

Example measurement for 16 stations after full database initialization:

| Metric | Result |
|---|---:|
| Total time | 13.09 s |
| HTTP requests | 49 |
| Current-data requests | 43 |
| Archival requests | 6 |
| Fetched records | 1540 |
| New records | 6 |
| Current-data request time | 5.31 s |
| Archival request time | 4.51 s |
| Database write time | 0.02 s |
| Aggregation time | 0.09 s |

Part of the total execution time also comes from intentional delays between archival requests.

For 6 archival requests, with a `0.5 s` delay, this adds approximately 3 extra seconds.

### Archival Requests

In a standard run, the 6 archival requests are made for sensors whose latest available measurements are significantly older than the current-data range.

The system detects a gap and attempts to fill it using the archival endpoint.

If GIOŚ does not provide newer data for a given sensor, the latest date remains unchanged and another attempt may be made during the next refresh.

### First Refresh After Initialization

The first refresh after building the database from scratch was significantly longer because the system had to fill larger historical gaps.

Result:

| Metric | Result |
|---|---:|
| Total time | 296.68 s |
| HTTP requests | 112 |
| Current-data requests | 43 |
| Archival requests | 69 |
| Archive uses | 32 |
| Fetched records | 19050 |
| New records | 19023 |
| Daily aggregates | 34353 |

The next run returned to the normal refresh mode:

| Metric | Result |
|---|---:|
| Total time | 13.09 s |
| HTTP requests | 49 |
| Archival requests | 6 |
| New records | 6 |
| Errors | 0 |

This confirms stable behavior after the initial data catch-up.


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

The production model uses:

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


## 8. Coverage and Model v3

Daily coverage (`coverage`) is calculated and stored in the `daily_measurements` table.

An experimental model v3 was also tested with additional features:

- `coverage_lag_1d`,
- `coverage_mean_3d`,
- `coverage_mean_7d`.

The purpose was to provide the model with information about whether a daily average was calculated from a complete day of measurements or only from a partial set of observations.

Model v3 results:

| Model | MAE | RMSE |
|---|---:|---:|
| Linear Regression | 5.752 | 8.532 |
| Random Forest | 5.617 | 8.890 |

Comparison with model v2:

| Model | Version | MAE | RMSE |
|---|---|---:|---:|
| Linear Regression | v2 | 5.693 | 8.468 |
| Linear Regression | v3 | 5.752 | 8.532 |
| Random Forest | v2 | 5.599 | 8.843 |
| Random Forest | v3 | 5.617 | 8.890 |

Adding coverage information did not improve the evaluation metrics in the current experiment.

Model v3 was kept as an experimental version, while model v2 remains the production model.


## 9. Data Freshness

If the latest measurement is no more than 2 days old, the data receives the status:

`fresh`

If the data is older, it receives the status:

`stale`

The forecast can still be generated, but the user receives a warning that older data was used.


## 10. Time Handling

GIOŚ measurement data is normalized to UTC before being stored in the database.

For data provided in local time, the following timezone is used:

`Europe/Warsaw`

This allows the system to account for:

- CET winter time,
- CEST summer time,
- the daylight saving time change in March,
- the daylight saving time change in October.

Both current and archival data pass through the same function that prepares records for database storage.

Historical data from parquet files is also converted from local time to UTC.

If an ambiguous timestamp occurs during the transition from summer time to winter time, the record is skipped instead of being arbitrarily assigned to one of the two possible hours.


## 11. Model and Cache

The production model is stored in:

`models/model_v2.joblib`

The model is kept in application memory, so it does not have to be loaded again for every forecast request.

The system checks the modification time of the model file.

If the file changes after retraining, the new version is automatically loaded during the next forecast request.

If the file has not changed, the model is retrieved from cache.

This mechanism is covered by a test.

An experimental model also exists:

`models/model_v3.joblib`

It uses features related to daily measurement coverage.


## 12. Tests

The project includes tests covering, among other things:

- API,
- cache,
- data cleaning,
- daily aggregation,
- feature building,
- GIOŚ integration,
- heating season logic,
- upsert behavior,
- model cache.

The current test suite contains 16 tests.

The upsert test confirms that saving a measurement again for the same sensor and timestamp:

- does not create a duplicate,
- updates the existing measurement value.

A full test starting from an empty database was also performed.

The initialization process successfully created:

- 288 stations,
- 525 PM sensors,
- 659680 historical measurements,
- 421248 weather records,
- 34346 daily aggregates.

Further refresh runs were then performed to verify process stability and idempotent behavior.


## 13. Dashboard

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


## 14. Future Development

The next stage of the project is containerization.

Planned goal:

- run the API, dashboard and update process in Docker,
- automatically prepare the application during the first startup,
- preserve SQLite data between container restarts,
- allow the entire project to be started with a single command.

Target workflow:

    git clone
        │
        ▼
    docker compose up
        │
        ▼
    working API + dashboard

Further possible improvements:

- automatic periodic execution of the updater,
- limiting repeated unsuccessful archival requests,
- further aggregation optimization,
- expanding the training dataset with more historical data,
- increasing the number of monitoring stations included in the system,
- further experiments with model features,
- improving forecast quality for high PM concentrations.