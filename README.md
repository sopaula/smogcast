# SmogCast

SmogCast is an air quality monitoring and forecasting application for selected monitoring stations in Poland.

The application combines air quality data from GIOŚ with weather data from Open-Meteo. It provides current and historical PM10 and PM2.5 measurements, next-day forecasts and air quality assessment.

**Live demo:** [SmogCast Dashboard](https://smogcast-dashboard.victorioussmoke-b065b7f6.polandcentral.azurecontainerapps.io/)

## Features

- current PM10 and PM2.5 measurements
- historical measurement charts
- next-day PM10 and PM2.5 forecasts
- air quality assessment based on GIOŚ thresholds
- weather data integration
- data coverage quality monitoring
- automatic daily data refresh
- Streamlit dashboard
- FastAPI backend
- SQLite and PostgreSQL support
- Docker-based local environment
- CI with GitHub Actions
- deployment in Microsoft Azure

## Architecture

SmogCast is divided into modules responsible for data ingestion, processing, storage, forecasting, API communication and visualization.

```text
GIOŚ API ───────┐
                ├──> Ingest ──> Processing ──> Database
Open-Meteo ─────┘                           │
                                            ├──> ML model
                                            │
                                            └──> FastAPI ──> Streamlit
```

The production environment uses PostgreSQL, while SQLite is available for quick local development.

## Tech stack

- Python 3.12
- FastAPI
- Streamlit
- SQLAlchemy
- PostgreSQL
- SQLite
- scikit-learn
- Docker / Docker Compose
- GitHub Actions
- Microsoft Azure

## Data

Air quality measurements are obtained from the public GIOŚ API.

Historical and forecast weather data are provided by Open-Meteo.

The project uses a prepared historical dataset covering approximately three years of measurements. The dataset is distributed through the GitHub Release `data-v1` and its files are verified using SHA256 checksums.

## Forecasting

The model predicts next-day PM10 and PM2.5 concentrations using historical pollution measurements and weather data.

The model uses features based on:

- previous PM measurements
- rolling PM averages
- calendar variables
- temperature
- wind speed
- relative humidity

More information about the model and its evaluation is available in the project documentation.

## Quick start

Clone the repository:

```bash
git clone https://github.com/sopaula/smogcast.git
cd smogcast
```

Install dependencies:

```bash
uv sync
```

### Local development with SQLite

Run the application:

```bash
DATABASE_URL=sqlite:///smogcast.db PYTHONPATH=src uv run python scripts/run_app.py
```

### Docker Compose

The complete local environment with PostgreSQL can be started with:

```bash
docker compose up --build
```

Available services:

- Dashboard: `http://localhost:8501`
- API: `http://localhost:8000`
- API documentation: `http://localhost:8000/docs`

To stop the environment:

```bash
docker compose down
```

## Production

The production version is deployed in Microsoft Azure using:

- Azure Container Apps
- Azure Database for PostgreSQL
- Azure Container Registry
- Managed Identity
- GitHub Actions

Production data are refreshed automatically once per day.

## Tests

Run tests:

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

## Documentation

More detailed project documentation is available in the `docs` directory:

- [System design](docs/design.md) – application architecture, module responsibilities, data flow, database structure and main technical decisions
- [Model report](docs/model_report.md) – dataset preparation, features, model training, evaluation, results and model limitations
- [Technical debt](docs/technical_debt.md) – known limitations, implementation compromises and possible future improvements

## License

This project is licensed under the MIT License.
