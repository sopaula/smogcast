## Baseline Results

A temporal split was used to evaluate the baseline models.

- Training set: 23,012 rows
- Test set: 11,336 rows

### Persistence Baseline

The persistence baseline assumes that the next day's pollution level will be equal to the previous day's value.

- MAE: 6.104
- RMSE: 9.680
- N: 11,336

### Climatology Baseline

The climatology baseline predicts the historical monthly average for a given station and pollutant, calculated using the training data only.

- MAE: 8.074
- RMSE: 12.414
- N: 11,336

The persistence baseline performed better than the climatology baseline and will be used as the main reference point for evaluating the machine learning models.

The model was trained on data before 2025-08-20 and evaluated on data from 2025-08-20 onward, preserving the chronological order of observations.



## Machine Learning Results

The models were evaluated using a temporal holdout. Data before 2025-08-20 were used for training, while data from 2025-08-20 onward were used for testing.

- Training rows before feature filtering: 23,012
- Test rows: 11,336
- Training rows after removing missing features: 22,788
- Test rows after removing missing features: 11,336

### Linear Regression

- MAE: 5.693
- RMSE: 8.468

### Random Forest

- MAE: 5.599
- RMSE: 8.843

### Comparison with Baselines

| Model | MAE | RMSE |
|---|---:|---:|
| Persistence | 6.104 | 9.680 |
| Climatology | 8.074 | 12.414 |
| Linear Regression | 5.693 | 8.468 |
| Random Forest | 5.599 | 8.843 |

Random Forest achieved the lowest MAE and was selected as the final model. Both machine learning models outperformed the persistence and climatology baselines on the one-year temporal holdout.

Although Random Forest achieved the lowest MAE, Linear Regression achieved a slightly lower RMSE, indicating that Random Forest may produce larger errors on some individual observations.


## Final Evaluation

The final model was evaluated on a one-year temporal holdout from 2025-08-20 onward.

### Overall Results

| Model | MAE | RMSE |
|---|---:|---:|
| Random Forest | 5.599 | 8.843 |
| Persistence baseline | 6.104 | 9.680 |
| Global mean baseline | 10.200 | 14.625 |

The Random Forest model outperformed both the persistence baseline and the global mean baseline.

### Prediction Variability

The model does not simply predict a constant or average value.

- Prediction standard deviation: 13.437
- Minimum prediction: 3.116
- Maximum prediction: 120.859
- Unique predictions: 11,336

The predictions vary substantially across observations, and the model performs much better than a constant global-mean prediction.

### Seasonal Evaluation

| Season | N | Model MAE | Model RMSE | Persistence MAE | Persistence RMSE |
|---|---:|---:|---:|---:|---:|
| Winter | 2,861 | 9.716 | 14.168 | 10.564 | 15.131 |
| Spring | 2,916 | 5.250 | 7.575 | 5.819 | 8.751 |
| Summer | 2,658 | 2.797 | 3.815 | 2.985 | 4.212 |
| Autumn | 2,901 | 4.456 | 6.049 | 4.849 | 6.864 |

The model outperformed the persistence baseline in every season.

Prediction errors were highest during winter and lowest during summer. This is consistent with the greater variability and higher pollution levels observed during the heating season.


## Error Analysis

Additional error analysis was performed to better understand the differences between Random Forest and Linear Regression, especially for large prediction errors, winter observations, and high pollution concentrations.

The analysis used the same temporal split as the main model evaluation.

Because the `daily_measurements` table had been updated with the latest available observations before running this analysis, the test set contained 11,364 rows instead of the previously reported 11,336. The resulting overall metrics remained almost unchanged.

### Updated Overall Comparison

| Model | MAE | RMSE |
|---|---:|---:|
| Random Forest | 5.596 | 8.836 |
| Linear Regression | 5.691 | 8.463 |

Random Forest still achieved the lower MAE, while Linear Regression achieved the lower RMSE.


### Largest Prediction Errors

To compare the most difficult cases, the worst 5% of absolute prediction errors were analyzed separately for both models.

| Model | 95th percentile absolute error | Mean absolute error in worst 5% |
|---|---:|---:|
| Random Forest | 17.132 | 27.376 |
| Linear Regression | 16.059 | 25.355 |

Linear Regression produced smaller errors among the most difficult 5% of observations.

This helps explain why Linear Regression achieved a lower RMSE despite having a slightly worse overall MAE. RMSE penalizes large individual errors more strongly than MAE.


### Winter Model Comparison

Winter was analyzed separately because it was the most difficult season in the previous evaluation.

| Model | Winter MAE | Winter RMSE |
|---|---:|---:|
| Random Forest | 9.716 | 14.168 |
| Linear Regression | 8.990 | 12.905 |

Linear Regression performed better than Random Forest on both MAE and RMSE during winter.

This suggests that the Linear Regression model is less affected by some of the large winter prediction errors, even though Random Forest performs slightly better on average across the complete test set.


### High Concentration Analysis

The behavior of the models at high pollution concentrations was also analyzed.

High concentrations were initially defined as observations in the highest 10% of actual target values in the test set.

For these observations:

- Random Forest mean signed error: -8.264 µg/m³
- Linear Regression mean signed error: -11.428 µg/m³
- Random Forest underestimated the true concentration in 76.5% of cases
- Linear Regression underestimated the true concentration in 81.9% of cases

A negative signed error means that the predicted value was lower than the observed value.

Both models therefore show a clear tendency to underestimate high pollution concentrations.

However, Random Forest underestimates high concentrations less strongly and less frequently than Linear Regression.


### High PM10 Concentrations

High PM10 concentrations were defined as the highest 10% of actual PM10 observations.

The threshold was:

`41.710 µg/m³`

Number of analyzed observations:

`570`

Results:

| Model | Mean signed error | Underestimation rate |
|---|---:|---:|
| Random Forest | -10.671 | 79.3% |
| Linear Regression | -13.595 | 83.3% |

Both models frequently underestimate high PM10 concentrations.

Random Forest shows a smaller negative bias than Linear Regression.


### High PM2.5 Concentrations

High PM2.5 concentrations were defined as the highest 10% of actual PM2.5 observations.

The threshold was:

`31.542 µg/m³`

Number of analyzed observations:

`567`

Results:

| Model | Mean signed error | Underestimation rate |
|---|---:|---:|
| Random Forest | -5.302 | 72.0% |
| Linear Regression | -8.878 | 80.1% |

The same tendency is visible for PM2.5.

Both models underestimate high concentrations, but Random Forest does so less frequently and with a smaller average negative error.


### Final Model Choice

The extended analysis shows that neither model is clearly superior in every aspect.

Linear Regression:

- achieves lower overall RMSE,
- produces smaller errors among the worst 5% of predictions,
- performs better during winter.

Random Forest:

- achieves lower overall MAE,
- underestimates high PM10 and PM2.5 concentrations less strongly,
- underestimates high concentrations less frequently.

Because Smogcast is intended to forecast air pollution, prediction quality during high-pollution episodes is particularly important.

For this reason, Random Forest remains the selected production model despite the stronger RMSE and winter performance of Linear Regression.

The tendency of both models to underestimate high pollution concentrations should be treated as an important limitation and as a potential area for future model improvement.


## Leakage Review

### PM lag features

The lag and rolling features were manually checked for a sample station.

- `pm_lag_1d` uses the previous day's PM value.
- `pm_mean_3d` uses only the previous three observations.
- `pm_mean_7d` uses only previous observations.

No target-day PM value is included in these features.

### Weather features

Weather features are merged using the same date as the prediction target.

This means that historical observed weather for the target day is used during training and evaluation.

In a real forecasting scenario, the true weather for the target day would not yet be known. A weather forecast available before the target day would need to be used instead.

This should be treated as a deployment limitation and reviewed carefully for potential leakage.