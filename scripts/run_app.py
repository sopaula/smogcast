import subprocess
import sys
import time


# Uruchamia pojedynczy skrypt i czeka na zakończenie.
def run_script(path):
    subprocess.run(
        [
            sys.executable,
            path,
        ],
        check=True,
    )


def main():
    print("Starting SmogCast...")

    # Przygotowuje bazę lub wznawia przerwaną inicjalizację.
    print("\nChecking database initialization...")

    run_script("scripts/init_db.py")

    # Aktualizuje dane przed uruchomieniem aplikacji.
    print("\nRefreshing data...")

    run_script("scripts/refresh_all.py")

    # Uruchamia API.
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

    # Daje API chwilę na uruchomienie.
    time.sleep(2)

    # Uruchamia dashboard.
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
