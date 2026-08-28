from smogcast.ingest.gios import get_all_stations
from smogcast.processing.filters import filter_silesian_stations


def main():
    stations = get_all_stations()
    silesian_stations = filter_silesian_stations(stations)

    print("ID | Nazwa stacji | Szerokość | Długość")
    print("-" * 70)

    print(f"Liczba stacji: {len(silesian_stations)}")

    for station in silesian_stations:
        print(
            station["Identyfikator stacji"],
            "|",
            station["Nazwa stacji"],
            "|",
            station["WGS84 φ N"],
            "|",
            station["WGS84 λ E"],
        )


if __name__ == "__main__":
    main()
