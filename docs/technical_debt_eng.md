# Decisions and Technical Debt

## 1. Purpose

This document summarizes the main technical decisions made during the development of SmogCast, the areas that were intentionally simplified, the current technical debt and possible directions for further development.

The goal is to document not only what was implemented, but also what was consciously left for later.

## 2. Key technical decisions

### 2.1. Limited set of monitoring stations

SmogCast currently uses 16 selected monitoring stations in Poland instead of all available GIOŚ stations.

This decision reduced the amount of data that had to be downloaded, processed and stored during development.

It also made model training, debugging and deployment easier to manage.

The current architecture can be extended to support more stations in the future.

### 2.2. SQLite and PostgreSQL environments

SmogCast supports multiple database configurations:

- SQLite for quick local development,
- PostgreSQL in the local Docker Compose environment,
- Azure Database for PostgreSQL in production.

SQLite keeps quick local development simple and allows the application to run without additional infrastructure.

The Docker environment uses PostgreSQL so that database-specific behavior can be tested locally before deployment.

The application uses the `DATABASE_URL` environment variable to select the database and falls back to SQLite when the variable is not provided.

### 2.3. Data refresh separated from user requests

Data ingestion was separated from dashboard loading and forecast generation.

The main refresh process is handled by:

```text
scripts/refresh_all.py
```

This avoids downloading large amounts of data every time a user opens the dashboard or requests a forecast.

For the production environment, the refresh process is executed automatically by GitHub Actions once per day.

This keeps application response times lower and reduces unnecessary calls to external APIs.

### 2.4. Daily refresh through GitHub Actions

A scheduled GitHub Actions workflow is used for production data updates instead of maintaining an additional continuously running Azure service.

This keeps the deployment simpler and reduces the amount of cloud infrastructure required for the project.

The workflow can also be triggered manually when needed.

A refresh is marked as fully successful only when all required update steps complete successfully.

The timestamp of the last successful refresh is stored in the database.

### 2.5. Local updater in Docker Compose

For local Docker usage, an `updater` service periodically refreshes current data.

This keeps local Docker execution independent from GitHub Actions and allows the complete application workflow to be tested locally.

### 2.6. One Docker image for API and dashboard

The API and dashboard use the same application image.

Different commands are used to start FastAPI and Streamlit.

This reduces duplication in the deployment process and means that dependencies only need to be maintained in one image.

The trade-off is that the image contains dependencies needed by both components, even when a particular container does not use all of them.

### 2.7. Azure Container Apps scaling

The deployed API and dashboard use Azure Container Apps.

Scale-to-zero was tested as a way to reduce cloud resource usage.

The main trade-off is that the first request after scaling from zero may be slower because a new container replica needs to start.

During active testing, minimum replicas can be kept above zero to avoid cold-start latency.

The scaling configuration can therefore be adjusted depending on whether lower cost or faster response time is more important.

### 2.8. Azure for Students deployment

The deployment was created using an Azure for Students subscription.

The infrastructure was configured with cost reduction in mind.

The project does not assume that every Azure service is free. Services such as PostgreSQL, Container Registry, Container Apps and logging may consume available Azure credit.

### 2.9. Managed Identity for container registry access

Azure Managed Identity is used to allow the Container Apps to pull images from Azure Container Registry.

The ACR administrator account was disabled after the deployment configuration was completed.

This avoids storing registry username and password credentials in the application configuration.

### 2.10. Secrets outside the repository

The production database connection string is not stored in the Git repository.

It is stored as a secret in the deployment environment and referenced through the `DATABASE_URL` environment variable.

The GitHub Actions workflow also uses a GitHub repository secret for the production database connection.

This prevents production credentials from being committed to source control.

### 2.11. Health and readiness checks

A `/health` endpoint is available for basic process health checks.

A separate `/ready` endpoint verifies whether the application is ready to serve forecast requests, including access to required application resources such as the database and model.

The Docker setup uses API health status before starting dependent services.

Azure Container Apps can also use health probes to detect unhealthy application revisions.

This improves startup reliability and makes application state easier to monitor.

### 2.12. Random Forest as the production forecasting model

Random Forest was selected as the production forecasting model.

Linear Regression achieved a lower RMSE and performed better in winter and among the largest prediction errors.

Random Forest was nevertheless selected because it achieved the lower overall MAE and showed a smaller tendency to underestimate high PM10 and PM2.5 concentrations.

Because elevated pollution levels are particularly important in the context of SmogCast, this behavior was considered relevant when selecting the production model.

### 2.13. Coverage kept as a quality indicator

Additional model features describing measurement coverage were tested.

They did not improve the evaluation metrics, so they were not included in the production model.

Coverage information was retained as a quality indicator because it still provides useful information about the completeness of the underlying measurements.

### 2.14. Local PostgreSQL environment

Docker Compose provides a local PostgreSQL database in addition to the SQLite development mode.

This allows the complete application flow to be tested against the same database engine used in production.

It also makes it possible to verify PostgreSQL-specific behavior such as:

- upserts,
- conflict handling,
- timezone-aware timestamps,
- schema initialization,
- database constraints.

This reduces differences between local testing and production deployment.

### 2.15. Versioned historical dataset

Prepared historical Parquet files are distributed through a versioned GitHub Release.

The current dataset version is:

```text
data-v1
```

The application first checks whether the required files already exist locally.

If they are missing, it attempts to download the prepared dataset from GitHub Release.

If the release is unavailable, the historical dataset can be rebuilt directly from GIOŚ and Open-Meteo.

The initialization strategy is therefore:

```text
local files
    ↓
GitHub Release
    ↓
full rebuild from source APIs
```

This provides a fast startup path while preserving reproducibility from the original data sources.

### 2.16. Dataset metadata and integrity verification

The prepared historical dataset includes metadata describing:

- dataset version,
- date range,
- data sources,
- timezone,
- processing version,
- number of records,
- SHA256 checksums.

The metadata are stored in:

```text
data/dataset_metadata.json
```

Downloaded Parquet files are verified using SHA256 before they are used.

This reduces the risk of using incomplete or corrupted dataset files and makes the initialization process more reproducible.

### 2.17. Weather forecasts stored before prediction requests

Next-day weather forecasts are fetched during the refresh process and stored in the database.

Each stored forecast includes:

- station identifier,
- target date,
- temperature,
- wind speed,
- relative humidity,
- fetch timestamp.

Forecast requests first look for weather data already stored for the exact target date.

If the required forecast is missing, the application can fetch it from Open-Meteo as a fallback and persist the result.

This reduces normal forecast request latency and removes the need to call Open-Meteo during most user requests.

### 2.18. Resumable database initialization

Database initialization is divided into separate stages.

Completed stages are stored in initialization state and do not need to be repeated on every startup.

This makes long initialization processes safer and allows interrupted initialization to continue without rebuilding everything from the beginning.

## 3. Current technical debt

### 3.1. Weather data mismatch between evaluation and production

During historical model evaluation, observed weather for the target date is used.

In production, only forecast weather for the following day is available.

This creates a difference between offline evaluation conditions and the real forecasting environment.

The current evaluation may therefore be somewhat more optimistic than actual production performance.

A stronger future evaluation should reproduce the production scenario using archived weather forecasts if such data are available.

### 3.2. Underestimation of high pollution concentrations

Both tested machine learning models tend to underestimate high PM10 and PM2.5 concentrations.

Random Forest performs better than Linear Regression in this area, but the problem remains.

This is especially important because high-pollution episodes are among the most important cases for an air-quality forecasting application.

Future model development should focus specifically on improving performance for high concentrations.

### 3.3. Winter prediction quality

The largest prediction errors occur during winter.

Pollution concentrations during the heating season are more variable and can reach significantly higher values than during the rest of the year.

The current model does not fully capture this variability.

### 3.4. No automatic model retraining

The production model is trained during initialization if the model file does not exist.

There is currently no scheduled production retraining process.

As new observations are collected, the model therefore does not automatically learn from them.

For a longer-running production system, periodic retraining should be added.

### 3.5. No model performance monitoring after deployment

The application does not currently compare historical forecasts with the measurements that later become available.

This means that model degradation cannot be automatically detected.

A future version could store and evaluate forecasts using rolling metrics such as:

- MAE,
- RMSE,
- bias,
- performance by season,
- performance for high pollution concentrations.

### 3.6. Limited number of stations

The current model and application operate on 16 selected monitoring stations.

This was sufficient for the project scope, but the system has not been validated for all GIOŚ stations.

Adding more stations would increase geographic coverage but would also require additional testing, data processing and model evaluation.

### 3.7. Dependence on external APIs

SmogCast depends on:

- GIOŚ,
- Open-Meteo.

Temporary API outages, slow responses or changes in response structure may affect ingestion and refresh processes.

Retries and error handling are implemented, but temporary failures can still prevent a complete refresh.

More advanced resilience mechanisms could be added if the system were expected to operate continuously at larger scale.

### 3.8. Single shared application image

Using one Docker image for both API and dashboard simplifies deployment, but it also produces a larger image than two highly optimized component-specific images would require.

For the current project size, simplicity was preferred over image optimization.

If startup time or registry storage became important, separate images could be considered.

### 3.9. Basic monitoring

Azure Log Analytics is available and refresh failures can be surfaced through GitHub Actions.

The project still does not include advanced operational monitoring dashboards for all components.

Additional monitoring could include:

- repeated API errors,
- unavailable external APIs,
- unhealthy Container App revisions,
- unusually long requests,
- database connection failures,
- model loading failures.

For the current project scope, logs, health checks and workflow failure notifications provide the basic operational visibility.

### 3.10. Public application without authentication

The deployed dashboard is publicly accessible.

This is intentional because the current application only exposes public air-quality and weather information.

No user accounts or authentication system were implemented.

If private functionality or administrative actions were added later, authentication and authorization would need to be introduced.

### 3.11. No custom domain

The production version currently uses the default Azure Container Apps address.

A custom domain was not added because it was not necessary for the functional requirements of the project and would introduce additional configuration.

### 3.12. PostgreSQL integration tests not yet included in CI

The application can be tested locally against PostgreSQL through Docker Compose.

However, the GitHub Actions CI pipeline does not yet run dedicated PostgreSQL integration tests.

Adding a temporary PostgreSQL service to the CI workflow would allow database-specific behavior to be checked automatically for every Pull Request.

Such tests should cover areas including:

- schema initialization,
- SQLAlchemy models,
- upserts,
- conflict handling,
- timezone-aware dates,
- initialization state,
- forecast weather storage.

### 3.13. Startup and initialization responsibilities

The project has separate scripts for:

```text
prepare_assets.py
init_db.py
refresh_all.py
run_app.py
```

The Docker environment separates these responsibilities through dedicated services.

The quick local `run_app.py` workflow still combines initialization, refresh and application startup in one convenience script.

This is useful for development but creates more startup responsibilities in a single process.

A future version could separate these operations even more explicitly.

### 3.14. Historical dataset release updates are manual

The prepared historical dataset is currently versioned and stored in GitHub Releases.

Creating a new dataset version, generating checksums and publishing updated release assets is still a manual process.

For the current project, dataset versions are expected to change infrequently, so this is acceptable.

If datasets were updated regularly, release creation and metadata generation could be automated.

## 4. Decisions intentionally deferred

Several possible improvements were consciously left outside the current project scope.

### Automatic retraining

Automatic retraining would require decisions about:

- retraining frequency,
- model validation,
- replacement criteria,
- model versioning,
- rollback when a new model performs worse.

For the current project, retaining a known evaluated model was safer and simpler.

### Full coverage of all GIOŚ stations

Supporting every station would increase data volume and project complexity.

The selected 16 stations were sufficient for demonstrating the complete data and forecasting pipeline.

### More advanced forecasting models

More complex approaches such as gradient boosting, dedicated time-series models or neural networks were not required to demonstrate the forecasting process.

Random Forest and Linear Regression already provided meaningful improvements over simple baselines and allowed detailed error analysis.

### Complex cloud infrastructure

The project does not use Kubernetes, message queues or separate microservices for every processing stage.

The current architecture was intentionally kept proportional to the size of the project.

### Authentication

Authentication was not implemented because the application displays public environmental data and currently has no private user functionality.

### Automatic historical dataset publishing

Prepared datasets are currently published manually as versioned GitHub Release assets.

An automated dataset build and release pipeline was not required for the current project scale.

## 5. What should be improved next

The most useful next improvements would be:

1. add PostgreSQL integration tests to the CI pipeline,
2. reproduce production weather conditions during model evaluation,
3. improve predictions for high PM10 and PM2.5 concentrations,
4. improve winter prediction performance,
5. implement automatic model performance monitoring,
6. add periodic model retraining,
7. expand operational monitoring and alerts,
8. expand the number of supported monitoring stations,
9. further separate initialization and application startup responsibilities,
10. automate dataset metadata and release generation if dataset versions become more frequent.

## 6. Current architecture

The current application uses separate ingestion, storage, prediction and presentation layers.

```text
GIOŚ API ───────────────┐
                        │
                        ├──> scheduled refresh
                        │         │
Open-Meteo ─────────────┘         │
                                  ▼
                             PostgreSQL
                                  │
                 ┌────────────────┴────────────────┐
                 │                                 │
          PM measurements                 weather forecasts
                 │                                 │
                 └──────────────┬──────────────────┘
                                │
                                ▼
                         feature generation
                                │
                                ▼
                            ML model
                                │
                                ▼
                            FastAPI
                                │
                                ▼
                           Streamlit
```

Prepared historical data used during initialization follow a separate bootstrap flow:

```text
local Parquet files
        │
        ▼
files available?
   │           │
  yes          no
   │           │
   │           ▼
   │     GitHub Release data-v1
   │           │
   │      available?
   │        │      │
   │       yes     no
   │        │      │
   │        │      ▼
   │        │   GIOŚ + Open-Meteo
   │        │   full rebuild
   │        │
   └────────┴──────────> database initialization
```

## 7. Possible future architecture

A future version could extend the current architecture with model monitoring and automatic retraining.

```text
stored forecasts
      │
      ├──> observed measurements
      │
      ▼
model performance monitoring
      │
      ├── MAE
      ├── RMSE
      ├── bias
      ├── winter performance
      └── high-pollution performance
      │
      ▼
retraining decision
      │
      ▼
candidate model
      │
      ▼
validation
      │
      ├── reject
      │
      └── deploy
```

A more mature version could also introduce automated dataset versioning:

```text
GIOŚ + Open-Meteo
        │
        ▼
historical rebuild
        │
        ▼
data validation
        │
        ▼
metadata + SHA256
        │
        ▼
versioned dataset release
```

## 8. Summary

The current SmogCast version provides a complete working pipeline from historical data preparation and ingestion to a publicly deployed forecasting application.

The project supports:

- quick local development using SQLite,
- a complete local PostgreSQL environment using Docker Compose,
- prepared versioned historical datasets,
- fallback dataset reconstruction from source APIs,
- PostgreSQL production storage in Azure,
- scheduled production data updates,
- cached next-day weather forecasts,
- FastAPI and Streamlit deployment,
- health and readiness checks,
- automated CI and refresh workflows.

Several decisions were made to keep the system understandable, maintainable and appropriate for the scope of the project.

The most important unresolved areas are related to:

- PostgreSQL integration testing in CI,
- model performance during high-pollution events,
- winter prediction errors,
- the difference between historical observed weather used in evaluation and forecast weather used in production,
- lack of automatic model retraining,
- lack of automatic model performance monitoring.

These limitations are known and documented rather than hidden.

The current version can therefore be treated as a functional production-style prototype with clearly identified areas for further development.