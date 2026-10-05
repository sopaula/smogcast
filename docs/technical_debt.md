# SmogCast – Technical Debt and Design Decisions

## 1. Purpose

This document summarizes the main technical decisions made during the development of SmogCast, the areas intentionally simplified for the current project scope, and the most important remaining technical debt.

The goal is to make known limitations and trade-offs explicit rather than hiding them.

## 2. Key Technical Decisions

### Limited set of monitoring stations

SmogCast currently uses 16 selected monitoring stations in Poland instead of all available GIOŚ stations.

This reduces:

- data volume,
- initialization time,
- model training time,
- deployment complexity,
- debugging complexity.

The architecture can be extended to support more stations in the future.

### SQLite and PostgreSQL support

The application supports:

- SQLite for quick local development,
- PostgreSQL in the local Docker Compose environment,
- Azure Database for PostgreSQL in production.

The database is selected using the `DATABASE_URL` environment variable.

This allows lightweight development with SQLite while still testing PostgreSQL-specific behavior locally before deployment.

### Data refresh separated from user requests

Data ingestion is separated from dashboard loading and forecast generation.

The main refresh process is handled by:

```text
scripts/refresh_all.py
```

In production, it is executed automatically once per day using GitHub Actions.

This avoids downloading external data during normal dashboard and forecast requests and reduces response time.

### Weather forecasts stored in advance

Next-day weather forecasts are downloaded during the refresh process and stored in the database.

Forecast requests first use the stored weather data.

If the required forecast is missing, the application can query Open-Meteo as a fallback and persist the result.

This reduces latency and limits unnecessary calls to the external weather API.

### One Docker image for API and dashboard

FastAPI and Streamlit use the same Docker image but different startup commands.

This simplifies:

- dependency management,
- image building,
- deployment.

The trade-off is that each container includes dependencies required by both application components.

For the current project size, deployment simplicity was preferred over image-size optimization.

### Managed Identity for Azure Container Registry

Azure Managed Identity is used by Container Apps to access Azure Container Registry.

The registry administrator account is disabled.

This avoids storing registry usernames and passwords in the deployment configuration.

### Secrets outside the repository

Production credentials are not stored in Git.

The database connection string is passed through environment variables and deployment secrets.

GitHub Actions also uses repository secrets for production access.

### Versioned historical dataset

Prepared historical Parquet files are distributed through the GitHub Release:

```text
data-v1
```

The application uses the following strategy:

```text
local files
    ↓
GitHub Release
    ↓
full rebuild from GIOŚ and Open-Meteo
```

Dataset metadata include SHA256 checksums, which are verified before downloaded files are used.

This provides faster initialization while preserving reproducibility from the original data sources.

### Resumable initialization

Database initialization is divided into stages.

Completed stages are stored in `initialization_state`, allowing interrupted initialization to continue without repeating every previous step.

### Random Forest as the production model

Random Forest was selected as the production forecasting model.

Linear Regression achieved a lower RMSE and performed better during winter and among the largest errors.

Random Forest was selected because it achieved:

- lower overall MAE,
- lower negative bias for high PM10 and PM2.5 concentrations,
- fewer underestimations during high-pollution episodes.

Since high pollution levels are particularly important for the SmogCast use case, this behavior was prioritized.

### Coverage as a quality indicator

Measurement coverage was tested as an additional model feature.

It did not improve model performance, so it was not included in the production model.

Coverage is still exposed as a data-quality indicator because it provides useful information about the completeness of recent measurements.

## 3. Current Technical Debt

### Weather data mismatch between evaluation and production

During historical model evaluation, observed weather for the target day is used.

In production, only forecast weather for the following day is available.

This means that offline evaluation does not exactly reproduce production conditions and may be somewhat optimistic.

A stronger evaluation should use archived weather forecasts if suitable historical forecast data are available.

### Underestimation of high pollution concentrations

Both evaluated machine learning models tend to underestimate high PM10 and PM2.5 concentrations.

Random Forest performs better than Linear Regression in this area, but the problem remains.

Future model development should focus specifically on improving performance during high-pollution episodes.

### Winter prediction quality

The largest prediction errors occur during winter.

Pollution concentrations during the heating season are more variable and often significantly higher than during other seasons.

The current model does not fully capture this variability.

### No automatic model retraining

The production model is not retrained automatically as new observations are collected.

The current version uses a known and evaluated model rather than replacing it automatically.

A future retraining pipeline would require:

- a retraining schedule,
- model validation,
- model versioning,
- replacement criteria,
- rollback support.

### No automatic model performance monitoring

The application does not currently compare stored historical forecasts with measurements that become available later.

Because of this, model degradation cannot be automatically detected.

Future monitoring could calculate rolling metrics such as:

- MAE,
- RMSE,
- prediction bias,
- winter performance,
- high-pollution performance.

### Limited number of stations

The current application and model use 16 selected monitoring stations.

The system has not been evaluated for all GIOŚ stations.

Increasing geographic coverage would require additional:

- data processing,
- testing,
- model evaluation,
- infrastructure resources.

### Dependence on external APIs

SmogCast depends on:

- GIOŚ,
- Open-Meteo.

Temporary outages, slow responses or changes in API response structures can affect refresh operations.

Retries and error handling are implemented, but external failures can still result in incomplete updates.

### Basic operational monitoring

The current deployment provides:

- application logs,
- health checks,
- readiness checks,
- GitHub Actions workflow status,
- Azure Container Apps health information.

More advanced monitoring could include alerts for:

- repeated API errors,
- external API outages,
- unhealthy Container App revisions,
- long response times,
- database connection failures,
- model loading failures.

### Public application without authentication

The dashboard is publicly accessible.

This is intentional because it exposes public environmental information and does not currently contain private user functionality.

If administrative or private features are introduced in the future, authentication and authorization should be added.

### No custom domain

The production application currently uses the default Azure Container Apps domain.

A custom domain was not required for the project scope and would introduce additional configuration and maintenance.

### Shared application image

Using one Docker image for both FastAPI and Streamlit simplifies deployment but produces a larger image than separate optimized images would.

Separate images could be introduced if startup time, image size or dependency isolation became more important.

### Local startup script combines several responsibilities

The quick local workflow uses:

```text
scripts/run_app.py
```

to coordinate multiple setup and startup operations.

This is convenient for development, but it combines several responsibilities in one workflow.

Docker Compose already separates these responsibilities more clearly into dedicated services.

### Historical dataset releases are manual

The historical dataset is versioned and stored in GitHub Releases.

Creating a new dataset version, generating metadata and publishing release assets is currently a manual process.

This is acceptable because dataset releases are infrequent.

If they become more frequent, the process could be automated.

## 4. Improvements Already Completed

Several areas that were previously considered technical debt have already been addressed.

### PostgreSQL integration testing

PostgreSQL integration tests are now included in the GitHub Actions CI workflow.

This allows database-specific behavior to be checked automatically before changes are merged into `main`.

### Production weather cache

Weather data required for next-day forecasts are now fetched in advance and stored in PostgreSQL.

This reduces forecast latency and dependency on Open-Meteo during normal user requests.

### Historical dataset integrity verification

Prepared dataset files are verified using SHA256 checksums before they are used.

### Local PostgreSQL environment

Docker Compose provides PostgreSQL locally, allowing development and integration testing against the same database engine used in production.

### Health and readiness endpoints

The API exposes:

```text
/health
/ready
```

These endpoints allow basic application health and dependency readiness to be checked independently.

### Production deployment

The application is deployed in Microsoft Azure using:

- Azure Container Apps,
- Azure Database for PostgreSQL,
- Azure Container Registry,
- Managed Identity.

Both the API and dashboard run as separate Container Apps.

## 5. Intentionally Deferred Improvements

The following improvements were consciously left outside the current project scope.

### Automatic retraining

Automatic retraining would add significant complexity related to validation, model replacement and rollback.

For the current project, retaining a known evaluated production model is safer and easier to reason about.

### Full GIOŚ station coverage

Supporting every available station would increase both data volume and model complexity.

The selected 16 stations are sufficient to demonstrate the full ingestion, processing, forecasting and deployment pipeline.

### More advanced forecasting models

More complex approaches such as:

- gradient boosting,
- dedicated time-series models,
- neural networks

could be explored in future work.

Random Forest and Linear Regression were sufficient to demonstrate meaningful improvement over baseline approaches and support detailed error analysis.

### More complex cloud architecture

The project intentionally does not use infrastructure such as:

- Kubernetes,
- message queues,
- multiple processing microservices.

The current Azure Container Apps architecture is more appropriate for the scale and goals of the project.

### Authentication

Authentication was not implemented because the current application exposes only public environmental information.

### Automatic dataset publishing

An automated historical dataset build and GitHub Release pipeline was not necessary for the current project scale.

## 6. Recommended Next Improvements

The highest-priority future improvements are:

1. reproduce production weather conditions during model evaluation,
2. improve predictions for high PM10 and PM2.5 concentrations,
3. improve winter prediction performance,
4. implement model performance monitoring,
5. introduce periodic model retraining with validation,
6. expand operational monitoring and alerts,
7. evaluate the system on a larger number of monitoring stations,
8. automate dataset publishing if dataset versions become more frequent.

## 7. Summary

SmogCast currently provides a complete working pipeline from historical data preparation and ingestion to a publicly deployed forecasting application.

The project includes:

- SQLite and PostgreSQL development environments,
- Docker Compose,
- versioned historical datasets,
- SHA256 integrity verification,
- scheduled production data refresh,
- stored weather forecasts,
- machine learning forecasts,
- FastAPI and Streamlit,
- CI with PostgreSQL integration tests,
- Microsoft Azure deployment,
- health and readiness checks.

The most important remaining technical debt is related mainly to model quality and long-term operation rather than missing core functionality.

The key unresolved areas are:

- high-pollution underestimation,
- larger winter prediction errors,
- the weather-data mismatch between evaluation and production,
- lack of automatic model retraining,
- lack of automatic model performance monitoring.

The current version can therefore be treated as a functional production-style prototype with clearly documented limitations and possible directions for further development.