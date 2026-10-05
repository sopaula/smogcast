# SmogCast – Design Document

## 1. Goal

SmogCast is an application for monitoring and forecasting air quality for selected monitoring stations in Poland.

The system combines:

- air quality measurements from GIOŚ,
- historical and forecast weather data from Open-Meteo,
- PostgreSQL as the main database,
- SQLite for quick local development,
- a machine learning model for next-day PM10 and PM2.5 forecasts,
- FastAPI as the backend,
- Streamlit as the dashboard.

The architecture separates data ingestion, storage, forecasting and presentation so that the dashboard does not depend directly on external APIs during normal use.

## 2. Architecture

Main application flow:

```text
GIOŚ API ───────┐
                ├──> Ingest ──> Processing ──> Database
Open-Meteo ─────┘                           │
                                            ├──> ML model
                                            │
                                            └──> FastAPI ──> Streamlit
```

The application is divided into modules responsible for:

- data ingestion,
- data processing,
- database access,
- feature preparation,
- forecasting,
- API communication,
- dashboard visualization.

Data refreshing is separated from both the dashboard and forecast requests.

The dashboard communicates with FastAPI and does not fetch measurements directly from GIOŚ.

## 3. Data Sources

### GIOŚ

GIOŚ provides:

- monitoring station metadata,
- sensor metadata,
- PM10 and PM2.5 measurements,
- current and archival measurement data.

The application uses selected monitoring stations from different locations in Poland.

### Open-Meteo

Open-Meteo provides:

- historical weather data,
- next-day weather forecasts.

Weather variables used by the forecasting model include:

- temperature,
- wind speed,
- relative humidity.

## 4. Database

SmogCast uses SQLAlchemy and supports both SQLite and PostgreSQL.

### SQLite

SQLite is available for quick local development and debugging.

If `DATABASE_URL` is not provided, the application can use:

```text
sqlite:///smogcast.db
```

### PostgreSQL

PostgreSQL is used:

- locally through Docker Compose,
- in production through Azure Database for PostgreSQL.

Using PostgreSQL locally allows database-specific behavior to be tested before deployment.

## 5. Data Schema

### stations

Stores monitoring station metadata.

| Column | Role | Description |
|---|---|---|
| `id` | PK | station identifier |
| `name` | | station name |
| `city` | | city |
| `latitude` | | latitude |
| `longitude` | | longitude |

### sensors

Stores sensors assigned to monitoring stations.

| Column | Role | Description |
|---|---|---|
| `id` | PK | sensor identifier |
| `station_id` | FK | station identifier |
| `param_code` | | parameter code |

A station may have multiple sensors.

### measurements

Stores raw PM10 and PM2.5 measurements.

The combination:

```text
(sensor_id, timestamp)
```

is unique.

If GIOŚ returns the same measurement again with a corrected value, the existing record is updated instead of creating a duplicate.

Missing measurements remain `NULL` and are not replaced with zero.

### weather

Stores historical weather data for station locations.

The forecasting model uses:

- temperature,
- wind speed,
- relative humidity.

### daily_measurements

Stores daily aggregates used by the forecasting model.

The table contains:

- station identifier,
- parameter,
- date,
- daily mean,
- daily maximum,
- data coverage.

Coverage describes how much valid measurement data was available for a given day.

### weather_forecasts

Stores weather forecasts required for next-day pollution forecasts.

The stored data include:

- station identifier,
- target date,
- temperature,
- wind speed,
- humidity,
- fetch timestamp.

Forecast requests first use weather data already stored in the database.

If the required forecast is missing, it can be fetched from Open-Meteo and persisted as a fallback.

### predictions

The database contains a table intended for storing generated predictions.

Currently, forecasts are generated on demand and returned through the API.

### initialization_state

Stores information about completed initialization stages so that long-running setup steps do not have to be repeated unnecessarily.

## 6. Data Initialization

Initial setup is handled by:

```text
scripts/init_db.py
```

The initialization process:

1. creates database tables,
2. stores station and sensor metadata,
3. imports historical GIOŚ measurements,
4. imports historical Open-Meteo weather data,
5. creates daily aggregates.

Prepared historical data are distributed through the GitHub Release `data-v1`.

Before use, downloaded files are verified using SHA256 checksums.

If prepared data are unavailable, the project can rebuild the historical dataset from the original sources.

## 7. Data Refresh

Current production data are refreshed by:

```text
scripts/refresh_all.py
```

The refresh process:

1. reads configured stations from the database,
2. retrieves recent PM10 and PM2.5 measurements,
3. fills older gaps using archival GIOŚ data when needed,
4. stores measurements using upsert logic,
5. recalculates affected daily aggregates,
6. retrieves next-day weather forecasts,
7. records the time of the last successful refresh.

The refresh process is designed to be idempotent. Running it again does not create duplicate measurements.

Production refresh is executed automatically once per day using GitHub Actions.

## 8. Forecasting Flow

For each pollutant, the forecast process:

1. checks the latest available measurement,
2. verifies data freshness,
3. retrieves recent daily aggregates,
4. retrieves the stored next-day weather forecast,
5. builds model features,
6. generates the prediction,
7. returns forecast metadata and data-quality information.

PM10 and PM2.5 are forecast independently.

Detailed information about the model, training process, evaluation and experimental versions is available in `model_report.md`.

## 9. Data Freshness and Coverage

The application tracks both data freshness and recent measurement coverage.

If recent measurement data are older than expected, the forecast can still be generated, but the API returns a warning.

Seven-day coverage is used as a data-quality indicator and is exposed together with forecast results.

Coverage is not used as an input feature of the production model.

## 10. Time Handling

GIOŚ measurement timestamps are normalized to UTC before being stored in the database.

Local Polish time is interpreted using:

```text
Europe/Warsaw
```

This handles both CET and CEST as well as daylight saving time transitions.

Current, archival and historical data use the same normalization approach.

## 11. API

The dashboard communicates only with FastAPI.

Main endpoints include:

### `GET /stations`

Returns stations available in the application.

### `GET /stations/{station_id}/measurements`

Returns measurement history for a selected pollutant and date range.

### `GET /stations/{station_id}/latest`

Returns the latest valid PM10 and PM2.5 measurements.

### `GET /stations/{station_id}/forecast`

Returns the next-day PM10 and PM2.5 forecast.

Forecast requests use data already stored in the database and do not refresh GIOŚ measurements directly.

### `GET /health`

Basic application health endpoint.

### `GET /ready`

Checks whether the API, database and model are ready to serve requests.

## 12. Dashboard

The Streamlit dashboard allows the user to:

- view monitoring stations on a map,
- switch between PM10 and PM2.5,
- select a station,
- view latest measurements,
- view next-day forecasts,
- view historical measurements,
- see data-quality warnings,
- switch between light and dark mode.

Air quality is interpreted using official GIOŚ air quality thresholds.

The dashboard displays information from FastAPI and does not connect directly to the production database.

## 13. Local Environment

The project supports two local workflows.

### SQLite

A lightweight setup for quick development and debugging.

### Docker Compose

The complete local environment includes:

- PostgreSQL,
- initialization service,
- data updater,
- FastAPI,
- Streamlit.

This environment is closer to production and is used to test PostgreSQL-specific behavior before deployment.

## 14. Production Deployment

The production environment is hosted in Microsoft Azure.

It uses:

- Azure Container Apps for FastAPI and Streamlit,
- Azure Database for PostgreSQL,
- Azure Container Registry,
- Managed Identity for registry access,
- GitHub Actions for scheduled data refresh.

The API and dashboard are deployed as separate Container Apps.

Production flow:

```text
GIOŚ / Open-Meteo
       │
       ▼
GitHub Actions
       │
       ▼
refresh_all.py
       │
       ▼
Azure PostgreSQL
       │
       ▼
FastAPI
       │
       ▼
Streamlit
```

## 15. Testing and CI

The project includes tests for areas such as:

- API behavior,
- data cleaning,
- daily aggregation,
- feature preparation,
- GIOŚ integration,
- upsert behavior,
- model caching,
- PostgreSQL integration.

GitHub Actions runs CI checks for Pull Requests to `main`.

The CI workflow includes:

- Ruff,
- pytest,
- PostgreSQL integration tests.

Changes must pass the required CI checks before they can be merged into `main`.

## 16. Related Documentation

More detailed information is available in:

- `model_report.md` – model preparation, training, evaluation, results and limitations,
- `technical_debt.md` – known limitations, implementation compromises and possible future improvements.
