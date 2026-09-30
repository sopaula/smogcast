# SmogCast

SmogCast is an air quality monitoring and forecasting application for selected stations in Poland.

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
- Docker-based application deployment,
- automated CI checks with GitHub Actions.

## Data sources

- GIOŚ – air quality measurements,
- Open-Meteo – historical and forecast weather data.

The project uses 16 selected monitoring stations in Poland.

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

For local development, install dependencies:

```bash
uv sync
```

## Running the application locally

Run:

```bash
PYTHONPATH=src uv run python scripts/run_app.py
```

On the first run, SmogCast automatically:

1. downloads the required historical GIOŚ and Open-Meteo data,
2. initializes the local SQLite database,
3. creates daily aggregates,
4. trains the forecasting model if it does not exist,
5. downloads the latest measurements,
6. starts the API and dashboard.

The first startup may take longer because historical data for the period from August 2023 to August 2026 must be downloaded and processed.

On subsequent runs, existing historical files, completed initialization steps and the trained model are reused.

## Running with Docker

The recommended way to run the complete application is Docker Compose.

Start all services:

```bash
docker compose up
```

Docker Compose starts:

- `init` – prepares historical data, initializes the database and trains the model if necessary,
- `updater` – periodically refreshes current data,
- `api` – FastAPI backend,
- `dashboard` – Streamlit frontend.

Historical data, the SQLite database and the trained model are stored in Docker volumes, so they are preserved between container restarts.

The initialization process is resumable and is skipped when the required data and model already exist.

To stop the application:

```bash
docker compose down
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

The API container includes a health check. The dashboard starts only after the API is reported as healthy.

## Forecasting

The forecasting model predicts next-day PM10 and PM2.5 concentrations using historical pollution measurements and weather data.

The production model is stored locally as:

```text
models/model_v2.joblib
```

If the file does not exist, it is trained automatically during initialization.

Forecasts also include a 7-day data coverage quality indicator:

- `>= 75%` – good,
- `50–75%` – warning,
- `< 50%` – critical.

Coverage is used as a quality indicator and is not an input feature of the production model.

## Data updates

Recent measurements are downloaded from GIOŚ during data refresh.

The Docker `updater` service periodically runs the refresh process and checks for new measurements.

Sensors with incomplete archival data are marked as stale and can be retried after 24 hours.

## Database

SmogCast uses SQLite.

The database is configured with:

- WAL mode,
- `busy_timeout`,
- resumable initialization.

When running with Docker Compose, the database is stored in a persistent Docker volume.

The local database file is not stored in the repository.

## Tests

Run tests locally:

```bash
uv run pytest
```

Run Ruff:

```bash
uv run ruff check .
```

## Continuous Integration

GitHub Actions automatically runs CI checks for every Pull Request.

The CI pipeline checks:

- Ruff,
- pytest.

A Pull Request must pass the required CI check before it can be merged into `main`.

## Project structure

```text
smogcast/
├── .github/
│   └── workflows/
│       └── ci.yml
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