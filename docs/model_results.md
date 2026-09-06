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