# SmogCast – Model Report

## 1. Objective

The forecasting component of SmogCast predicts next-day PM10 and PM2.5 concentrations for selected monitoring stations in Poland.

The model uses historical air pollution measurements, weather data and calendar-related features.

The goal is not only to achieve a low average prediction error, but also to maintain useful performance during periods of elevated air pollution.

## 2. Data Split and Evaluation Strategy

The models were evaluated using a temporal holdout rather than a random train-test split.

Data before `2025-08-20` were used for training, while data from `2025-08-20` onward were used for testing.

This preserves the chronological order of observations and better reflects a real forecasting scenario.

Dataset sizes:

- training rows before feature filtering: `23,012`,
- training rows after removing missing features: `22,788`,
- test rows: `11,336`.

The main evaluation metrics were:

- **MAE – Mean Absolute Error** – the average absolute prediction error,
- **RMSE – Root Mean Squared Error** – a metric that penalizes large individual errors more strongly.

## 3. Baseline Models

Two simple baseline approaches were evaluated before testing machine learning models.

### Persistence baseline

The persistence baseline assumes that the next day's pollution level will be equal to the previous day's value.

| Metric | Result |
|---|---:|
| MAE | 6.104 |
| RMSE | 9.680 |

### Climatology baseline

The climatology baseline predicts the historical monthly average for a given station and pollutant using training data only.

| Metric | Result |
|---|---:|
| MAE | 8.074 |
| RMSE | 12.414 |

The persistence baseline performed better and was used as the main reference point for the machine learning models.

## 4. Model Comparison

Two main machine learning models were evaluated:

- Linear Regression,
- Random Forest.

Results on the temporal holdout:

| Model | MAE | RMSE |
|---|---:|---:|
| Persistence | 6.104 | 9.680 |
| Climatology | 8.074 | 12.414 |
| Linear Regression | 5.693 | 8.468 |
| Random Forest | 5.599 | 8.843 |

Both machine learning models outperformed the baseline approaches.

Random Forest achieved the lowest MAE, while Linear Regression achieved a slightly lower RMSE.

This means that Random Forest had the lower average absolute error, while Linear Regression handled some of the largest individual errors better.

## 5. Production Model

Random Forest was selected as the production model.

Its main evaluation results were:

| Model | MAE | RMSE |
|---|---:|---:|
| Random Forest | 5.599 | 8.843 |
| Persistence baseline | 6.104 | 9.680 |
| Global mean baseline | 10.200 | 14.625 |

The model therefore performed better than both the persistence baseline and a simple global-mean prediction.

The predictions also showed substantial variability:

- prediction standard deviation: `13.437`,
- minimum prediction: `3.116`,
- maximum prediction: `120.859`,
- unique predictions: `11,336`.

This confirms that the model does not simply return values close to a constant or average prediction.

## 6. Input Features

The model uses historical PM values, calendar-related features and weather data.

### Pollution-related features

- previous-day PM value,
- 3-day rolling mean,
- 7-day rolling mean.

### Calendar-related features

- month,
- day of week,
- weekend indicator,
- heating-season indicator.

### Weather features

- temperature,
- wind speed,
- relative humidity.

The PM lag and rolling features were checked for target leakage.

The review confirmed that:

- `pm_lag_1d` uses the previous day's PM value,
- `pm_mean_3d` uses only previous observations,
- `pm_mean_7d` uses only previous observations.

The target-day PM value is therefore not included in these features.

## 7. Seasonal Evaluation

The model was also evaluated separately for each season.

| Season | N | Random Forest MAE | Random Forest RMSE | Persistence MAE | Persistence RMSE |
|---|---:|---:|---:|---:|---:|
| Winter | 2,861 | 9.716 | 14.168 | 10.564 | 15.131 |
| Spring | 2,916 | 5.250 | 7.575 | 5.819 | 8.751 |
| Summer | 2,658 | 2.797 | 3.815 | 2.985 | 4.212 |
| Autumn | 2,901 | 4.456 | 6.049 | 4.849 | 6.864 |

Random Forest outperformed the persistence baseline in every season.

The largest errors occurred during winter, while the lowest errors occurred during summer.

This is consistent with the higher variability of pollution concentrations during the heating season.

## 8. Error Analysis

After the database had been updated with additional observations, the evaluation set increased to `11,364` rows.

The overall results remained almost unchanged:

| Model | MAE | RMSE |
|---|---:|---:|
| Random Forest | 5.596 | 8.836 |
| Linear Regression | 5.691 | 8.463 |

Random Forest still achieved the lower MAE, while Linear Regression retained the lower RMSE.

### Largest prediction errors

The worst 5% of predictions were analyzed separately.

| Model | 95th percentile absolute error | Mean absolute error in worst 5% |
|---|---:|---:|
| Random Forest | 17.132 | 27.376 |
| Linear Regression | 16.059 | 25.355 |

Linear Regression produced smaller errors among the most difficult observations.

This explains why its RMSE is lower despite its slightly worse overall MAE.

### Winter performance

Winter was the most difficult season for both models.

| Model | Winter MAE | Winter RMSE |
|---|---:|---:|
| Random Forest | 9.716 | 14.168 |
| Linear Regression | 8.990 | 12.905 |

Linear Regression performed better than Random Forest on both metrics during winter.

## 9. Performance at High Pollution Concentrations

Because SmogCast is intended to forecast air pollution, performance during high-concentration episodes is particularly important.

For observations in the highest 10% of actual pollution concentrations:

- Random Forest mean signed error: `-8.264 µg/m³`,
- Linear Regression mean signed error: `-11.428 µg/m³`,
- Random Forest underestimated the true concentration in `76.5%` of cases,
- Linear Regression underestimated the true concentration in `81.9%` of cases.

Both models therefore show a clear tendency to underestimate high pollution levels.

Random Forest performs better in this area because its negative bias is smaller and it underestimates high values less frequently.

### High PM10 concentrations

High PM10 observations were defined as the highest 10% of PM10 values.

Threshold:

`41.710 µg/m³`

Number of observations:

`570`

| Model | Mean signed error | Underestimation rate |
|---|---:|---:|
| Random Forest | -10.671 | 79.3% |
| Linear Regression | -13.595 | 83.3% |

Both models frequently underestimate high PM10 concentrations, but Random Forest shows a smaller negative bias.

### High PM2.5 concentrations

High PM2.5 observations were defined as the highest 10% of PM2.5 values.

Threshold:

`31.542 µg/m³`

Number of observations:

`567`

| Model | Mean signed error | Underestimation rate |
|---|---:|---:|
| Random Forest | -5.302 | 72.0% |
| Linear Regression | -8.878 | 80.1% |

The same tendency is visible for PM2.5.

Random Forest still underestimates high concentrations, but less strongly and less frequently than Linear Regression.

## 10. Final Model Choice

Neither model was clearly superior in every aspect.

### Linear Regression

Advantages:

- lower overall RMSE,
- smaller errors among the worst 5% of predictions,
- better winter performance.

### Random Forest

Advantages:

- lower overall MAE,
- smaller underestimation of high PM10 and PM2.5 concentrations,
- lower underestimation rate for high values.

Random Forest was therefore retained as the production model because performance during high-pollution episodes was considered particularly important for the SmogCast use case.

## 11. Coverage Feature Experiment

A third model version was tested with additional data coverage features:

- `coverage_lag_1d`,
- `coverage_mean_3d`,
- `coverage_mean_7d`.

These features describe how complete the daily PM measurements were.

Results:

| Model | Version | MAE | RMSE |
|---|---|---:|---:|
| Linear Regression | v2 | 5.693 | 8.468 |
| Linear Regression | v3 | 5.752 | 8.532 |
| Random Forest | v2 | 5.599 | 8.843 |
| Random Forest | v3 | 5.617 | 8.890 |

Adding coverage information did not improve the evaluation results.

Model v2 therefore remained the production version, while coverage information is used only as a data-quality indicator exposed together with the forecast.

## 12. Weather Data Limitation

An important difference was identified between the weather data used during model evaluation and the real production scenario.

During training and evaluation, weather features are joined using the same date as the prediction target. This means that historical observed weather for the target day is used.

In a real next-day forecasting scenario, the actual weather for the target day is not yet known.

The production application therefore relies on a weather forecast available before the target day.

Weather forecasts are fetched in advance and stored in the database. During prediction, the application first uses the stored forecast data. If the required weather forecast is missing, Open-Meteo can be queried as a fallback and the result is persisted.

The difference between observed weather used during evaluation and forecast weather used in production is an important methodological limitation.

Offline evaluation may therefore be somewhat more optimistic than real-world performance.

## 13. Model Limitations

### High pollution episodes

Both tested models tend to underestimate high PM10 and PM2.5 concentrations.

This is especially important because high-pollution episodes are among the most relevant situations from the user's perspective.

Random Forest performs better than Linear Regression in this area, but the underestimation problem remains.

### Winter performance

Prediction errors are significantly higher during winter than during other seasons.

Winter PM concentrations are more variable and often more extreme, making them harder to predict accurately.

### Weather data mismatch

Historical observed weather is used during model evaluation, while production forecasts rely on forecast weather.

As a result, offline evaluation may be somewhat more optimistic than real-world performance.

### Limited input variables

The model does not directly include several factors that may influence pollution levels, such as:

- traffic intensity,
- local emission sources,
- industrial activity,
- domestic heating behavior,
- more detailed atmospheric conditions,
- sudden local events.

### Limited spatial coverage

The current version of SmogCast uses 16 selected monitoring stations in Poland.

The model has therefore not been evaluated as a universal forecasting model for all GIOŚ stations.

### Dependence on external data sources

The application depends on GIOŚ and Open-Meteo availability and data quality.

Missing, delayed or incomplete input data may reduce forecast quality.

### Stale measurement data

If the newest PM measurements are older than expected, the application can still generate a forecast using the available data.

Such a forecast may be less reliable.

The system therefore exposes information about data freshness and warns the user when older observations are used.

## 14. Conclusions

The final Random Forest model improves on the simple persistence and climatology baselines and provides useful next-day PM10 and PM2.5 forecasts.

Its strongest advantage over Linear Regression is its behavior during high-pollution episodes, where it shows a smaller tendency to underestimate concentrations.

At the same time, the evaluation shows that the model is not equally accurate in all conditions.

The most important limitations are:

- higher errors during winter,
- underestimation of high pollution concentrations,
- the difference between observed weather used during evaluation and forecast weather available in production,
- dependence on the quality and freshness of external data.

For these reasons, SmogCast forecasts should be treated as estimates supporting air-quality monitoring rather than exact predictions of future pollutant concentrations.