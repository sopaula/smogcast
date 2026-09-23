from pathlib import Path

import joblib
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error

from smogcast.model.baseline import temporal_split
from smogcast.processing.features import build_features_from_db


CUTOFF_DATE = "2025-08-20"

MODEL_DIR = Path("models")
MODEL_PATH = MODEL_DIR / "model_v2.joblib"


FEATURE_COLUMNS = [
    "pm_lag_1d",
    "pm_mean_3d",
    "pm_mean_7d",
    "coverage_lag_1d",
    "coverage_mean_3d",
    "coverage_mean_7d",
    "month",
    "day_of_week",
    "is_weekend",
    "is_heating_season",
    "temp_c",
    "wind_ms",
    "humidity",
]


def prepare_xy(df):
    required_columns = FEATURE_COLUMNS + ["target_value"]

    clean_df = df.dropna(subset=required_columns).copy()

    clean_df["is_weekend"] = clean_df["is_weekend"].astype(int)

    clean_df["is_heating_season"] = clean_df["is_heating_season"].astype(int)

    X = clean_df[FEATURE_COLUMNS]
    y = clean_df["target_value"]

    return X, y


def calculate_metrics(y_true, y_pred):
    mae = mean_absolute_error(
        y_true,
        y_pred,
    )

    rmse = (
        mean_squared_error(
            y_true,
            y_pred,
        )
        ** 0.5
    )

    return {
        "mae": mae,
        "rmse": rmse,
    }


def train_models():
    print("Building features...")

    df = build_features_from_db()

    print("\nTemporal split")

    train_df, test_df = temporal_split(
        df,
        cutoff_date=CUTOFF_DATE,
    )

    print("Train rows:", len(train_df))
    print("Test rows:", len(test_df))

    X_train, y_train = prepare_xy(train_df)
    X_test, y_test = prepare_xy(test_df)

    print("\nRows after removing missing features")
    print("Train rows:", len(X_train))
    print("Test rows:", len(X_test))

    # Linear Regression
    print("\nTraining Linear Regression...")

    linear_model = LinearRegression()

    linear_model.fit(
        X_train,
        y_train,
    )

    linear_predictions = linear_model.predict(X_test)

    linear_metrics = calculate_metrics(
        y_test,
        linear_predictions,
    )

    print("\nLinear Regression")
    print(f"MAE:  {linear_metrics['mae']:.3f}")
    print(f"RMSE: {linear_metrics['rmse']:.3f}")

    # Random Forest
    print("\nTraining Random Forest...")

    random_forest_model = RandomForestRegressor(
        n_estimators=200,
        random_state=42,
        n_jobs=-1,
    )

    random_forest_model.fit(
        X_train,
        y_train,
    )

    random_forest_predictions = random_forest_model.predict(X_test)

    random_forest_metrics = calculate_metrics(
        y_test,
        random_forest_predictions,
    )

    print("\nRandom Forest")
    print(f"MAE:  {random_forest_metrics['mae']:.3f}")
    print(f"RMSE: {random_forest_metrics['rmse']:.3f}")

    # Select the best model based on MAE
    if random_forest_metrics["mae"] < linear_metrics["mae"]:
        best_model = random_forest_model
        best_model_name = "random_forest"
        best_metrics = random_forest_metrics
    else:
        best_model = linear_model
        best_model_name = "linear_regression"
        best_metrics = linear_metrics

    print("\nSelected model:")
    print(best_model_name)

    print(f"MAE:  {best_metrics['mae']:.3f}")
    print(f"RMSE: {best_metrics['rmse']:.3f}")

    # Save model
    MODEL_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    model_bundle = {
        "model": best_model,
        "model_name": best_model_name,
        "feature_columns": FEATURE_COLUMNS,
        "version": "v2",
        "cutoff_date": CUTOFF_DATE,
    }

    joblib.dump(
        model_bundle,
        MODEL_PATH,
    )

    print(f"\nModel saved to: {MODEL_PATH}")


if __name__ == "__main__":
    train_models()
