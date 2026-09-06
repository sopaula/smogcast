import joblib
from sklearn.metrics import mean_absolute_error, mean_squared_error

from smogcast.model.baseline import temporal_split
from smogcast.processing.features import build_features_from_db


MODEL_PATH = "models/model_v2.joblib"
CUTOFF_DATE = "2025-08-20"


def calculate_metrics(y_true, y_pred):
    mae = mean_absolute_error(y_true, y_pred)
    rmse = mean_squared_error(y_true, y_pred) ** 0.5

    return {
        "mae": mae,
        "rmse": rmse,
    }


def add_season(df):
    df = df.copy()

    def month_to_season(month):
        if month in [12, 1, 2]:
            return "winter"
        if month in [3, 4, 5]:
            return "spring"
        if month in [6, 7, 8]:
            return "summer"
        return "autumn"

    df["season"] = df["month"].apply(month_to_season)

    return df


def evaluate():
    print("Loading model...")

    model_bundle = joblib.load(MODEL_PATH)

    model = model_bundle["model"]
    feature_columns = model_bundle["feature_columns"]

    print("Building features...")

    df = build_features_from_db()

    train_df, test_df = temporal_split(
        df,
        cutoff_date=CUTOFF_DATE,
    )

    required_columns = feature_columns + [
        "target_value",
        "pm_lag_1d",
    ]

    test_df = test_df.dropna(subset=required_columns).copy()

    test_df["is_weekend"] = test_df["is_weekend"].astype(int)

    test_df["is_heating_season"] = test_df["is_heating_season"].astype(int)

    X_test = test_df[feature_columns]
    y_test = test_df["target_value"]

    model_predictions = model.predict(X_test)

    test_df["model_prediction"] = model_predictions

    # Persistence baseline
    test_df["persistence_prediction"] = test_df["pm_lag_1d"]

    # Global mean baseline
    global_mean = train_df["target_value"].mean()

    test_df["global_mean_prediction"] = global_mean

    print("\nOverall evaluation")

    model_metrics = calculate_metrics(
        y_test,
        test_df["model_prediction"],
    )

    persistence_metrics = calculate_metrics(
        y_test,
        test_df["persistence_prediction"],
    )

    mean_metrics = calculate_metrics(
        y_test,
        test_df["global_mean_prediction"],
    )

    print("\nModel")
    print(f"MAE:  {model_metrics['mae']:.3f}")
    print(f"RMSE: {model_metrics['rmse']:.3f}")

    print("\nPersistence baseline")
    print(f"MAE:  {persistence_metrics['mae']:.3f}")
    print(f"RMSE: {persistence_metrics['rmse']:.3f}")

    print("\nGlobal mean baseline")
    print(f"MAE:  {mean_metrics['mae']:.3f}")
    print(f"RMSE: {mean_metrics['rmse']:.3f}")

    # Check whether predictions vary
    print("\nPrediction variability")

    print(
        "Prediction standard deviation:",
        round(
            test_df["model_prediction"].std(),
            3,
        ),
    )

    print(
        "Prediction min:",
        round(
            test_df["model_prediction"].min(),
            3,
        ),
    )

    print(
        "Prediction max:",
        round(
            test_df["model_prediction"].max(),
            3,
        ),
    )

    print(
        "Unique predictions:",
        test_df["model_prediction"].nunique(),
    )

    # Seasonal evaluation
    test_df = add_season(test_df)

    print("\nSeasonal evaluation")

    for season in [
        "winter",
        "spring",
        "summer",
        "autumn",
    ]:
        season_df = test_df[test_df["season"] == season]

        if season_df.empty:
            continue

        season_model_metrics = calculate_metrics(
            season_df["target_value"],
            season_df["model_prediction"],
        )

        season_persistence_metrics = calculate_metrics(
            season_df["target_value"],
            season_df["persistence_prediction"],
        )

        print(f"\n{season.capitalize()}")

        print(f"N: {len(season_df)}")

        print(
            "Model MAE:",
            f"{season_model_metrics['mae']:.3f}",
        )

        print(
            "Model RMSE:",
            f"{season_model_metrics['rmse']:.3f}",
        )

        print(
            "Persistence MAE:",
            f"{season_persistence_metrics['mae']:.3f}",
        )

        print(
            "Persistence RMSE:",
            f"{season_persistence_metrics['rmse']:.3f}",
        )


if __name__ == "__main__":
    evaluate()
