# SmogCast

SmogCast is an air quality monitoring and forecasting application using GIOŚ air quality data and Open-Meteo weather data.

The project includes:

- GIOŚ data ingestion,
- Open-Meteo integration,
- SQLite storage,
- daily PM aggregation,
- PM10 and PM2.5 forecasting,
- FastAPI backend,
- Streamlit dashboard.

## Requirements

- Python 3.12+
- uv

## Installation

```bash
git clone <repository-url>
cd smogcast
uv sync
```

## Required local files

The first database initialization requires:

```text
data/raw/gios_pm_measurements_3y.parquet
data/raw/open_meteo_weather_3y.parquet
```

Forecasting requires:

```text
models/model_v2.joblib
```

These files are not committed to the repository.

## Run the application

The easiest way to start SmogCast locally is:

```bash
PYTHONPATH=src uv run python scripts/run_app.py
```

The script:

1. initializes or resumes database setup,
2. refreshes current GIOŚ data,
3. starts FastAPI,
4. starts the Streamlit dashboard.

After startup:

```text
API:       http://127.0.0.1:8000
API docs:  http://127.0.0.1:8000/docs
Dashboard: http://localhost:8501
```

Stop the application with `Ctrl+C`.

## Manual commands

Initialize the database:

```bash
PYTHONPATH=src uv run python scripts/init_db.py
```

Refresh current data:

```bash
PYTHONPATH=src uv run python scripts/refresh_all.py
```

Start FastAPI:

```bash
PYTHONPATH=src uv run uvicorn smogcast.api.main:app --reload
```

Start Streamlit:

```bash
PYTHONPATH=src uv run streamlit run src/smogcast/dashboard/app.py
```

## Forecast

The next-day forecast uses:

- previous-day PM value,
- 3-day PM mean,
- 7-day PM mean,
- calendar features,
- heating season information,
- Open-Meteo weather forecast.

Model v2 is the current production model.

Recent measurement coverage is used as a forecast quality indicator:

- `>= 75%` – good,
- `50–75%` – warning,
- `< 50%` – critical warning.

## Data update

The updater stores current GIOŚ data in SQLite.

Sensors without fresh archival data are marked as `stale`. Unsuccessful archival backfill is retried at most once every 24 hours.

## Database

SQLite uses:

```text
WAL
busy_timeout = 5000 ms
```

This improves concurrent reads and writes between the API and updater.

## Tests

```bash
uv run pytest
```

## Code quality

```bash
uv run ruff check .
uv run ruff format .
```

## Project structure

```text
smogcast/
├── data/
├── docs/
├── models/
├── scripts/
│   ├── init_db.py
│   ├── refresh_all.py
│   └── run_app.py
├── src/smogcast/
│   ├── api/
│   ├── dashboard/
│   ├── ingest/
│   ├── model/
│   ├── processing/
│   └── storage/
├── tests/
├── pyproject.toml
└── README.md
```

## Data sources

- Główny Inspektorat Ochrony Środowiska (GIOŚ)
- Open-Meteo

## License

This project is licensed under the MIT License.