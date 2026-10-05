# SmogCast

SmogCast is an air quality monitoring and forecasting application for selected monitoring stations in Poland.

The application combines air quality data from GIOŚ with weather data from Open-Meteo and provides current measurements, historical data and next-day PM10 and PM2.5 forecasts.

## Features

- current PM10 and PM2.5 measurements,
- historical measurement charts,
- next-day air quality forecasts,
- weather data integration,
- data coverage quality warnings,
- automatic refresh of recent measurements,
- Streamlit dashboard,
- FastAPI backend,
- SQLite support for quick local development,
- PostgreSQL support for Docker and production,
- Docker-based local environment,
- automated CI checks with GitHub Actions,
- daily production data refresh,
- deployment in Microsoft Azure.

## Architecture

SmogCast is divided into separate modules responsible for data ingestion, processing, storage, forecasting, API communication and visualization.

```text
GIOŚ API ───────┐
                ├──> Ingest ──> Processing ──> Database
Open-Meteo ─────┘                           │
                                            ├──> ML model
                                            │
                                            └──> FastAPI ──> Streamlit
```

Main application flow:

1. air quality data are downloaded from GIOŚ,
2. weather data are downloaded from Open-Meteo,
3. data are cleaned and processed,
4. processed data are stored in the database,
5. the forecasting model uses historical pollution and weather data,
6. FastAPI exposes application data through REST endpoints,
7. Streamlit communicates with the API and displays the dashboard.

The project supports:

- SQLite for quick local development,
- PostgreSQL for the Docker environment,
- Azure Database for PostgreSQL in production.

## Data sources

### GIOŚ

Air quality measurements are obtained from the public API of the Chief Inspectorate of Environmental Protection  
(Główny Inspektorat Ochrony Środowiska – GIOŚ) as part of the State Environmental Monitoring system.

Source:

Główny Inspektorat Ochrony Środowiska – Państwowy Monitoring Środowiska.

When reusing GIOŚ data, the source of the information must be clearly indicated.

The project uses 16 selected monitoring stations in Poland.

### Open-Meteo

Historical and forecast weather data are obtained from Open-Meteo.

Open-Meteo data are provided under the CC BY 4.0 licence and require attribution.

## Historical dataset

SmogCast uses a prepared historical dataset covering the period from August 2023 to August 2026.

The prepared dataset is published as the GitHub Release:

```text
data-v1
```

It contains:

```text
gios_pm_measurements_3y.parquet
open_meteo_weather_3y.parquet
dataset_metadata.json
```

Dataset metadata are also stored in the repository:

```text
data/dataset_metadata.json
```

The metadata file contains:

- dataset version,
- date range,
- data sources,
- timezone,
- number of records,
- processing version,
- SHA256 checksums.

Downloaded Parquet files are verified against their SHA256 checksums before use.

### Dataset preparation flow

When historical data are required, `scripts/prepare_assets.py` uses the following strategy:

```text
local Parquet files
        ↓
if missing
        ↓
GitHub Release data-v1
        ↓
if unavailable
        ↓
full rebuild from GIOŚ and Open-Meteo
```

This provides a fast default startup while preserving the ability to reproduce the dataset directly from the original sources.

## Requirements

### Local development

- Python 3.12+
- `uv`

### Docker

- Docker Desktop
- Docker Compose

## Installation

Clone the repository:

```bash
git clone https://github.com/sopaula/smogcast.git
cd smogcast
```

Install dependencies:

```bash
uv sync
```

## Quick local development

For quick local development, SmogCast can be run with SQLite:

```bash
DATABASE_URL=sqlite:///smogcast.db PYTHONPATH=src uv run python scripts/run_app.py
```

The startup script:

1. checks historical data,
2. downloads prepared Parquet files from GitHub Release if necessary,
3. falls back to a full rebuild if the prepared dataset is unavailable,
4. initializes the SQLite database,
5. creates daily aggregates,
6. trains the forecasting model if necessary,
7. refreshes recent data,
8. starts FastAPI and Streamlit.

Existing historical files, completed initialization steps and the trained model are reused on subsequent runs.

This mode is intended mainly for quick development and debugging.

## Running with Docker

Docker Compose provides the complete local environment using PostgreSQL.

Start all services:

```bash
docker compose up --build
```

Docker Compose starts:

- `postgres` – local PostgreSQL database,
- `init` – prepares historical data, initializes the database and trains the model if necessary,
- `updater` – periodically refreshes current data,
- `api` – FastAPI backend,
- `dashboard` – Streamlit frontend.

On a fresh environment:

```text
Docker Compose
      ↓
PostgreSQL
      ↓
prepare_assets.py
      ↓
GitHub Release data-v1
      ↓
Parquet verification
      ↓
database initialization
      ↓
API + dashboard
```

If the GitHub Release is unavailable, the historical dataset can be rebuilt directly from GIOŚ and Open-Meteo.

PostgreSQL data, historical assets and the trained model are stored in persistent Docker volumes.

The initialization process is resumable and previously completed steps are skipped when possible.

To stop the application:

```bash
docker compose down
```

To stop the application and remove local Docker volumes:

```bash
docker compose down -v
```

To check running services:

```bash
docker compose ps
```

## Application

Dashboard:

```text
http://localhost:8501
```

API:

```text
http://localhost:8000
```

API documentation:

```text
http://localhost:8000/docs
```

Health endpoint:

```text
/health
```

Readiness endpoint:

```text
/ready
```

The dashboard starts after the API is reported as healthy.

## Forecasting

The forecasting model predicts next-day PM10 and PM2.5 concentrations using historical pollution measurements and weather data.

The production model is stored as:

```text
models/model_v2.joblib
```

If the model does not exist during local initialization, it is trained automatically.

The model uses features based on:

- previous PM measurements,
- rolling PM averages,
- calendar variables,
- temperature,
- wind speed,
- relative humidity.

Forecasts also include a 7-day data coverage quality indicator:

- `>= 75%` – good,
- `50–75%` – warning,
- `< 50%` – low coverage warning.

Coverage is used as a data-quality indicator and is not an input feature of the production model.

## Weather forecast cache

Weather forecasts used for next-day PM predictions are stored in the database.

The refresh process downloads weather forecasts for the required target date and stores:

- station identifier,
- target date,
- temperature,
- wind speed,
- humidity,
- fetch timestamp.

Forecast requests first use the stored weather forecast.

If the required forecast is missing, the application can fetch it from Open-Meteo as a fallback and persist it in the database.

This avoids making an external weather API request during normal forecast requests.

## Data updates

### Local and Docker

The Docker `updater` service periodically runs:

```bash
python scripts/refresh_all.py
```

The refresh process updates:

- recent PM10 and PM2.5 measurements,
- daily aggregates,
- next-day weather forecasts.

Partial failures are reported and do not silently mark the whole refresh as successful.

### Production

Production data are updated using a scheduled GitHub Actions workflow.

The workflow runs:

```bash
PYTHONPATH=src uv run python scripts/refresh_all.py
```

once per day and updates the production PostgreSQL database.

The timestamp of the last fully successful refresh is stored in the database and exposed through the API.

## Database

SmogCast supports SQLite and PostgreSQL through SQLAlchemy.

The database connection is selected using:

```text
DATABASE_URL
```

### SQLite

SQLite is intended for quick local development.

If `DATABASE_URL` is not provided, the application can fall back to:

```text
sqlite:///smogcast.db
```

SQLite-specific configuration includes:

- WAL mode,
- `busy_timeout`.

### Local PostgreSQL

Docker Compose runs a local PostgreSQL instance.

This environment is used to test the application against the same database engine used in production.

It allows PostgreSQL-specific behavior such as:

- conflict handling,
- upserts,
- timezone-aware timestamps,
- schema initialization

to be tested locally before deployment.

### Production PostgreSQL

The deployed application uses Azure Database for PostgreSQL.

The production connection string is provided through the `DATABASE_URL` environment variable and is not stored in the repository.

## Deployment

The production version of SmogCast is deployed in Microsoft Azure.

The deployment uses:

- Azure Container Apps – FastAPI backend and Streamlit dashboard,
- Azure Database for PostgreSQL – production database,
- Azure Container Registry – Docker image storage,
- Managed Identity – secure access to the container registry,
- Log Analytics – application logs and monitoring,
- GitHub Actions – automatic daily data refresh.

The API and dashboard are deployed as separate Container Apps.

Production flow:

```text
GIOŚ / Open-Meteo
        ↓
GitHub Actions
        ↓
refresh_all.py
        ↓
Azure PostgreSQL
        ↓
FastAPI
        ↓
Streamlit
```

The Azure services use the existing PostgreSQL database and do not rebuild the historical dataset during normal application startup.

## Tests

Run tests locally:

```bash
uv run pytest
```

Run Ruff:

```bash
uv run ruff check .
```

Format code:

```bash
uv run ruff format .
```

## GitHub Actions

The repository uses GitHub Actions for continuous integration and production data refresh.

### Continuous Integration

For every Pull Request to `main`, the CI workflow runs automated project checks including:

- Ruff,
- pytest.

A Pull Request must pass the required checks before it can be merged into `main`.

### Daily ingest

A separate scheduled workflow runs once per day.

It:

1. checks out the repository,
2. installs Python and project dependencies,
3. connects to the production PostgreSQL database,
4. runs `scripts/refresh_all.py`,
5. updates recent measurements, daily aggregates and weather forecasts.

The workflow can also be started manually from GitHub Actions.

## Project structure

```text
smogcast/
├── .github/
│   └── workflows/
│       ├── ci.yml
│       └── ingest.yml
├── data/
│   └── dataset_metadata.json
├── scripts/
│   ├── prepare_assets.py
│   ├── init_db.py
│   ├── refresh_all.py
│   └── run_app.py
├── src/
│   └── smogcast/
│       ├── ingest/
│       ├── processing/
│       ├── storage/
│       ├── model/
│       ├── api/
│       └── dashboard/
├── tests/
├── docs/
├── models/
├── Dockerfile
├── docker-compose.yml
├── .dockerignore
├── pyproject.toml
└── README.md
```

## License

This project is licensed under the MIT License.