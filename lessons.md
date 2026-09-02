# Lessons Learned

## Project setup and repository structure

- A clear project structure makes it easier to separate responsibilities between data ingestion, processing, storage, modelling, API and presentation layers.
- Using `uv` simplifies Python environment and dependency management.
- Development tools such as Ruff, Pytest and pre-commit help detect formatting and code quality problems before changes are committed.
- A properly configured `.gitignore` is important to avoid committing local environments, raw data, cache files, secrets and local database files.
- Small, focused Git commits and feature branches make changes easier to review and understand.

## Working with external APIs

- External APIs should not be treated as perfectly reliable.
- Pagination must be handled explicitly when an endpoint returns data across multiple pages.
- Timeouts and temporary API errors can occur even when the implementation is correct.
- Retry logic and short delays between requests make ingestion more reliable.
- HTTP status code `429` should be handled because APIs may limit the number of requests.
- Large historical downloads are easier to manage when the requested period is divided into smaller date ranges.
- API response structures should be inspected before implementing parsers instead of assuming field names.

## GIOŚ data ingestion

- GIOŚ stations, sensors and measurements are separate resources and need to be connected using their identifiers.
- A station can contain multiple sensors measuring the same pollutant.
- Sensor metadata is necessary to determine which station and pollutant a measurement belongs to.
- Historical measurements are retrieved by sensor, so station and parameter information must later be added using sensor metadata.
- The original archival endpoint was not reliable enough for the required data volume, so the ingestion approach was adapted to use archival data by sensor.
- Some GIOŚ sensors provide hourly measurements while others provide daily measurements, so measurement frequency should not always be assumed to be hourly.

## Open-Meteo ingestion

- Weather data can be collected using station coordinates obtained from GIOŚ.
- Using the same station identifiers for air quality and weather data makes later merging easier.
- Historical weather was requested directly in UTC to simplify time alignment.
- Open-Meteo wind speed is returned in km/h when no different unit is explicitly requested.
- Raw API data can remain unchanged while unit conversion is performed when data is prepared for the application database.

## Exploratory data analysis

- A missing value and a missing timestamp are different problems.
- `isna()` only detects values that exist as rows with missing content. It does not detect measurements that were never returned by the API.
- Time differences between consecutive measurements can be used to detect gaps in time-series data.
- Measurement frequency should be determined per sensor because the dataset contains both hourly and daily sensors.
- Coverage analysis is useful for deciding which stations and sensors are suitable for modelling.
- Large pollution values should not automatically be treated as outliers because high PM values can represent real smog episodes.
- PM10 and PM2.5 distributions are right-skewed and contain high pollution peaks.
- Air pollution shows clear seasonality, with substantially higher PM concentrations during the heating season.
- Weekday and weekend distributions can differ, but statistical significance should be interpreted together with the actual size of the difference.
- With very large datasets, even relatively small differences may become statistically significant.
- Weather variables such as temperature and wind speed show useful relationships with PM concentrations, but correlation should not be interpreted as causation.

## Time zones

- Time zones must be handled explicitly when combining data from different sources.
- Open-Meteo historical data was requested in UTC.
- GIOŚ archival timestamps were explicitly converted from CET to UTC before being stored and merged.
- A timezone conversion can shift a timestamp to the previous calendar date in UTC, which is expected behaviour.
- Time handling should be implemented in production code rather than only inside exploratory notebooks.

## Data cleaning

- Data cleaning rules should be conservative when working with environmental measurements.
- Negative PM values are physically invalid and can be removed.
- High PM values should be preserved because they may represent genuine pollution events.
- Missing values should remain distinguishable from zero.
- Cleaning logic should be moved from notebooks into reusable functions.
- Unit tests are useful for confirming that cleaning removes only the values that are actually considered invalid.

## Database design

- SQLAlchemy models allow the database schema to be defined directly in Python code.
- Foreign keys represent relationships between stations, sensors, measurements and other tables.
- Database constraints provide an additional layer of data integrity beyond application logic.
- Measurements require a unique constraint on `(sensor_id, timestamp)`.
- Weather records require a unique constraint on `(station_id, timestamp)`.
- A missing measurement value should be stored as `NULL`, not as zero.
- `Base.metadata.create_all()` creates missing tables but does not automatically migrate existing tables after their schema changes.
- During early development, an empty table can be recreated after a schema change, but production systems should use proper database migrations.

## Idempotent ingestion

- Data ingestion should be idempotent whenever the same data may be processed more than once.
- An upsert performs an insert for a new record and an update when the unique key already exists.
- Stations and sensors can be upserted using their identifiers.
- Measurements can be upserted using `(sensor_id, timestamp)`.
- Weather can be upserted using `(station_id, timestamp)`.
- Running the same ingestion process twice should not increase the number of database rows.
- Idempotence should be verified both with automated tests and with real ingestion results.

## Metadata and time-series storage

- Metadata and time-series data do not need to cover exactly the same scope.
- The database can contain metadata for all available GIOŚ stations and sensors while historical measurements and weather are initially stored only for selected MVP stations.
- Keeping broad metadata allows the application to be expanded later without redesigning the database.
- The current database contains metadata for all available stations and PM sensors while historical time-series data covers the selected project dataset.

## Daily aggregation

- Hourly measurements can be transformed into daily records for modelling and visualisation.
- Daily aggregation groups measurements by station, pollutant and date.
- Daily statistics currently include mean value, maximum value and coverage.
- Missing values must be ignored when calculating the number of available measurements.
- Coverage is calculated as `(number of available hourly measurements / 24) × 100%`.
- Sensors with daily measurement frequency naturally receive low hourly coverage values, so sensor frequency may need to be considered later when selecting modelling data.
- Aggregation correctness should be tested on a small manually calculated example before running it on the full dataset.

## FastAPI backend

- FastAPI can expose database data without loading the entire database into Python memory.
- Filtering should be done in SQL queries whenever possible.
- Measurements need to be joined with sensor metadata because the `measurements` table stores `sensor_id`, while station and pollutant information is stored in `sensors`.
- `/stations/{id}/measurements` can return measurements for a specific station, pollutant and time range.
- `/stations/{id}/latest` can return the newest available measurement by sorting timestamps in descending order and limiting the query to one row.
- A missing station should produce HTTP `404`.
- Invalid query parameter types and unsupported parameter values can be validated automatically by FastAPI and Pydantic and result in HTTP `422`.
- FastAPI `/docs` provides automatically generated interactive OpenAPI documentation and is useful for manually testing endpoints during development.

## Testing

- Unit tests are useful for checking small isolated pieces of logic.
- Integration tests are needed to verify that multiple backend layers work together.
- SQLite in-memory databases make integration tests fast and independent of local project data.
- An integration test can verify metadata insertion, measurement insertion, database querying and idempotence in one flow.
- Tests should not rely on external APIs when the behaviour can be verified locally.
- Pre-commit hooks and Ruff help keep formatting and code quality consistent.
- Warnings from dependencies should be distinguished from actual failing tests.

## Git and code review

- Changes should be grouped into logical commits instead of one large commit.
- Feature branches make it easier to isolate work before merging it into `main`.
- Pre-commit may modify files during a commit attempt, requiring the changed files to be staged again before committing.
- A successful `git push` does not necessarily mean a new commit was created; the commit must succeed first.
- Pull requests provide a useful checkpoint for reviewing architecture, tests and unintended files before merging.
- Generated data and the local SQLite database should remain outside the repository.

## Current backend status

The current backend includes:

- GIOŚ station ingestion
- GIOŚ sensor ingestion
- historical PM10 and PM2.5 ingestion
- historical Open-Meteo weather ingestion
- explicit UTC handling
- SQLAlchemy database models
- idempotent upserts
- daily PM aggregation
- FastAPI endpoints returning real database data
- unit tests
- integration tests using SQLite in-memory

The local database currently contains:

- 288 stations
- 525 PM sensors
- 225,014 historical PM measurements
- 140,544 historical weather records
- 11,368 daily measurement aggregates