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

The project supports two database configurations:

- SQLite for local development,
- PostgreSQL for the deployed Azure environment.

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
docker compose up --build
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

The API includes a health check endpoint.

The dashboard starts only after the API is reported as healthy.

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

Recent measurements are downloaded from GIOŚ during the refresh process.

### Local and Docker

The Docker `updater` service periodically runs the refresh process and checks for new measurements.

Sensors with incomplete archival data are marked as stale and can be retried after 24 hours.

### Production

The deployed application uses a scheduled GitHub Actions workflow.

The workflow runs:

```bash
PYTHONPATH=src uv run python scripts/refresh_all.py
```

once per day and updates the production PostgreSQL database with recent data.

## Database

SmogCast supports two database configurations.

### Local development

SQLite is used by default.

If the `DATABASE_URL` environment variable is not provided, the application automatically falls back to:

```text
sqlite:///smogcast.db
```

The local database uses:

- WAL mode,
- `busy_timeout`,
- resumable initialization.

When running with Docker Compose, the database is stored in a persistent Docker volume.

The local database file is not stored in the repository.

### Production

The deployed version uses Azure Database for PostgreSQL.

The production database connection is provided through the `DATABASE_URL` environment variable and is stored as a secret in the Azure environment.

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

Both applications are configured with:

- `minReplicas = 0`,
- `maxReplicas = 1`.

This allows the applications to scale down when they are not being used.

The API uses a health check endpoint:

```text
/health
```

Public dashboard:

```text
...
```

## Known limitations

The first forecast request for a station may take longer because current weather forecast data are fetched from an external API.

In some cases, the first forecast request may time out. Retrying the request usually resolves the issue.

## Tests

Run tests locally:

```bash
uv run pytest
```

Run Ruff:

```bash
uv run ruff check .
```

## GitHub Actions

The repository uses GitHub Actions for continuous integration and automatic data refresh.

### Continuous Integration

For every Pull Request to `main`, the CI workflow runs:

- Ruff,
- pytest,
- Docker image build.

A Pull Request must pass the required CI checks before it can be merged into `main`.

### Daily ingest

A separate scheduled workflow runs once per day.

It:

1. checks out the repository,
2. installs Python and project dependencies,
3. connects to the production PostgreSQL database,
4. runs `scripts/refresh_all.py`,
5. updates recent measurement and weather data.

The workflow can also be started manually from GitHub Actions.

## Project structure

```text
smogcast/
├── .github/
│   └── workflows/
│       ├── ci.yml
│       └── ingest.yml
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
