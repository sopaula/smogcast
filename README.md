# Smogcast

Smogcast is an application for analysing air quality data and forecasting PM10 and PM2.5 pollution levels using GIOŚ air quality data and Open-Meteo weather data.

## Requirements

- Python 3.12+
- uv

## Installation

Install project dependencies:

```bash
uv sync
```

## Running the CLI

```bash
PYTHONPATH=src uv run python src/smogcast/cli.py
```

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

- `GET /health` – checks whether the API is running
- `GET /stations` – returns the list of stations stored in the database

## Running Tests

```bash
uv run pytest
```