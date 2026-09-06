import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error

from smogcast.processing.features import build_features_from_db


# Dzieli dane chronologicznie na zbiór treningowy i testowy.
# Późniejsze daty trafiają do holdoutu testowego.
def temporal_split(
    df: pd.DataFrame,
    cutoff_date: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    data = df.copy()

    data["date"] = pd.to_datetime(data["date"])

    cutoff = pd.Timestamp(cutoff_date)

    train = data[data["date"] < cutoff].copy().reset_index(drop=True)

    test = data[data["date"] >= cutoff].copy().reset_index(drop=True)

    return train, test


# Baseline persistence:
# prognoza na dany dzień jest równa wartości PM z poprzedniego dnia
def persistence_baseline(
    test: pd.DataFrame,
) -> pd.Series:
    return test["pm_lag_1d"]


# Baseline klimatologiczny:
# prognoza jest średnią historyczną dla stacji, parametru i miesiąca
# Średnie są liczone wyłącznie na zbiorze treningowym
def climatology_baseline(
    train: pd.DataFrame,
    test: pd.DataFrame,
) -> pd.Series:
    climatology = (
        train.groupby(
            [
                "station_id",
                "param_code",
                "month",
            ],
            as_index=False,
        )["target_value"]
        .mean()
        .rename(
            columns={
                "target_value": "climatology_prediction",
            }
        )
    )

    predictions = test.merge(
        climatology,
        on=[
            "station_id",
            "param_code",
            "month",
        ],
        how="left",
    )

    return predictions["climatology_prediction"]


# Oblicza MAE i RMSE dla podanych wartości rzeczywistych i prognoz
def calculate_metrics(
    y_true: pd.Series,
    y_pred: pd.Series,
) -> dict:
    valid = y_true.notna() & y_pred.notna()

    y_true_valid = y_true[valid]
    y_pred_valid = y_pred[valid]

    mae = mean_absolute_error(
        y_true_valid,
        y_pred_valid,
    )

    rmse = np.sqrt(
        mean_squared_error(
            y_true_valid,
            y_pred_valid,
        )
    )

    return {
        "mae": mae,
        "rmse": rmse,
        "n": len(y_true_valid),
    }


# Buduje cechy, wykonuje split czasowy i porównuje oba baseline'y na holdoucie
def evaluate_baselines():
    features = build_features_from_db()

    train, test = temporal_split(
        features,
        cutoff_date="2025-08-20",
    )

    persistence_predictions = persistence_baseline(test)

    persistence_metrics = calculate_metrics(
        test["target_value"],
        persistence_predictions,
    )

    climatology_predictions = climatology_baseline(
        train,
        test,
    )

    climatology_metrics = calculate_metrics(
        test["target_value"],
        climatology_predictions,
    )

    print("Temporal split")
    print(f"Train rows: {len(train)}")
    print(f"Test rows: {len(test)}")
    print()

    print("Persistence baseline")
    print(f"MAE:  {persistence_metrics['mae']:.3f}")
    print(f"RMSE: {persistence_metrics['rmse']:.3f}")
    print(f"N:    {persistence_metrics['n']}")
    print()

    print("Climatology baseline")
    print(f"MAE:  {climatology_metrics['mae']:.3f}")
    print(f"RMSE: {climatology_metrics['rmse']:.3f}")
    print(f"N:    {climatology_metrics['n']}")


if __name__ == "__main__":
    evaluate_baselines()
