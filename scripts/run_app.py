from pathlib import Path
import subprocess
import sys
import time


GIOS_PATH = Path("data/raw/gios_pm_measurements_3y.parquet")
WEATHER_PATH = Path("data/raw/open_meteo_weather_3y.parquet")
MODEL_PATH = Path("models/model_v2.joblib")


def run_script(path):
    subprocess.run(
        [
            sys.executable,
            path,
        ],
        check=True,
    )


def run_module(module):
    subprocess.run(
        [
            sys.executable,
            "-m",
            module,
        ],
        check=True,
    )


def main():
    print("Starting SmogCast...")

    # Przygotowuje brakujące dane historyczne.
    if not GIOS_PATH.exists() or not WEATHER_PATH.exists():
        print("\nPreparing historical data...")
        run_script("scripts/prepare_assets.py")

    print("\nChecking database initialization...")
    run_script("scripts/init_db.py")

    # Trenuje model przy pierwszym uruchomieniu.
    if not MODEL_PATH.exists():
        print("\nTraining forecasting model...")
        run_module("smogcast.model.train")

    print("\nRefreshing data...")
    run_script("scripts/refresh_all.py")

    print("\nStarting FastAPI...")

    api_process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "smogcast.api.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8000",
        ]
    )

    time.sleep(2)

    print("\nStarting Streamlit dashboard...")

    dashboard_process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            "src/smogcast/dashboard/app.py",
        ]
    )

    try:
        api_process.wait()
        dashboard_process.wait()

    except KeyboardInterrupt:
        print("\nStopping SmogCast...")

        api_process.terminate()
        dashboard_process.terminate()

        api_process.wait()
        dashboard_process.wait()


if __name__ == "__main__":
    main()
