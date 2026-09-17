# Smogcast

Smogcast is an application for analysing air quality data and forecasting PM10 and PM2.5 pollution levels using GIOŚ air quality data and Open-Meteo weather data.

The project contains:

- air quality data ingestion from GIOŚ,
- weather data integration with Open-Meteo,
- local SQLite storage,
- daily PM aggregation,
- machine learning forecasting,
- FastAPI backend,
- Streamlit dashboard.

The current architecture separates data updates from the dashboard and forecast process.

GIOŚ data is refreshed by a separate updater and stored in the local database. The dashboard and forecast endpoints use data already available in SQLite, so they do not wait for GIOŚ requests during normal usage.


## Requirements

- Python 3.12+
- uv


## Installation

Install project dependencies:

```bash
uv sync
```


## Initial Data Setup

The application uses a local SQLite database.

Historical PM and weather data can be loaded into the database using the project ingestion scripts and prepared Parquet files.

The database stores:

- stations,
- sensors,
- hourly PM measurements,
- historical weather data,
- daily PM aggregates,
- prediction-related data.


## Updating Current GIOŚ Data

Current PM10 and PM2.5 measurements are refreshed separately from the dashboard.

Run:

```bash
PYTHONPATH=src uv run python scripts/refresh_all.py
```

The updater:

- reads stations and sensors from the local database,
- downloads current PM10 and PM2.5 measurements from GIOŚ,
- stores only records newer than the latest measurement already available,
- uses the archival GIOŚ endpoint when an older gap must be filled,
- recalculates daily aggregates for sensors with new measurements.

The updater is independent from the dashboard and API requests.

During testing, refreshing all 16 stations completed in approximately 17.5 seconds without errors.


## Running the API

Start the FastAPI development server:

```bash
PYTHONPATH=src uv run uvicorn smogcast.api.main:app --reload
```

The API will be available at:

- `http://127.0.0.1:8000`
- health check: `http://127.0.0.1:8000/health`
- OpenAPI documentation: `http://127.0.0.1:8000/docs`


## Available API Endpoints

### Health check

```text
GET /health
```

Checks whether the API is running.


### Stations

```text
GET /stations
```

Returns stations with measurement data available in the local database.


### Measurements

```text
GET /stations/{station_id}/measurements
```

Returns PM measurements for the selected station.

Supported query parameters:

- `param` – `PM10` or `PM25`,
- `date_from` – optional start date,
- `date_to` – optional end date.

Example:

```text
GET /stations/117/measurements?param=PM10
```


### Latest measurements

```text
GET /stations/{station_id}/latest
```

Returns the latest available PM10 and PM2.5 measurements for the selected station.

Measurements with missing values are ignored.


### Forecast

```text
GET /stations/{station_id}/forecast
```

Returns the PM10 and PM2.5 forecast for the next day.

The forecast uses:

- daily PM measurements stored in SQLite,
- PM lag from the previous day,
- 3-day PM mean,
- 7-day PM mean,
- month,
- day of week,
- weekend information,
- heating season information,
- Open-Meteo temperature forecast,
- Open-Meteo wind speed forecast,
- Open-Meteo humidity forecast.

The forecast process does not refresh GIOŚ data.

It uses data already stored in the local database.

The response also contains information about the freshness of the PM data used for prediction.


## Running the Dashboard

First start the API:

```bash
PYTHONPATH=src uv run uvicorn smogcast.api.main:app --reload
```

Then open another terminal and start Streamlit:

```bash
uv run streamlit run src/smogcast/dashboard/app.py
```

The dashboard will be available at:

```text
http://localhost:8501
```

The dashboard contains:

- a map of available stations,
- PM10 and PM2.5 map views,
- latest measurements,
- measurement timestamps,
- station selection,
- next-day PM10 and PM2.5 forecasts,
- measurement history.

Measurement and forecast cards use three status colours:

- green – value clearly below the threshold,
- yellow – value close to the threshold,
- red – threshold exceeded.

The dashboard reads air quality data through the FastAPI backend and does not communicate directly with GIOŚ.


## Data Sources

Air quality data:

- Główny Inspektorat Ochrony Środowiska (GIOŚ)

Weather data:

- Open-Meteo

Historical weather data is used during model training.

Open-Meteo forecast data is used during next-day prediction.


## Machine Learning Model

The current forecasting model is stored as:

```text
models/model_v2.joblib
```

The same trained model structure is used to generate forecasts for PM10 and PM2.5.

PM10 and PM2.5 are processed independently.

The model is cached in application memory after the first load, so it does not need to be read from disk for every forecast request.


## Running Tests

Run all tests:

```bash
uv run pytest
```


## Code Quality

Run Ruff:

```bash
uv run ruff check .
```

Run formatting checks:

```bash
uv run ruff format .
```


## Project Structure

```text
smogcast/
├── data/
├── docs/
├── models/
├── notebooks/
├── scripts/
│   └── refresh_all.py
├── src/
│   └── smogcast/
│       ├── api/
│       ├── dashboard/
│       ├── ingest/
│       ├── model/
│       ├── processing/
│       └── storage/
├── tests/
├── pyproject.toml
└── README.md
```


## Current Data Flow

```text
GIOŚ
  │
  ▼
refresh_all.py
  │
  ▼
SQLite
  │
  ├──────────────► FastAPI ──────────────► Streamlit dashboard
  │
  └──────────────► daily measurements
                         │
                         ▼
                  forecasting model
                         ▲
                         │
                  Open-Meteo forecast
```

The updater, API, dashboard and forecasting process are separated so that external GIOŚ requests do not block the user interface.