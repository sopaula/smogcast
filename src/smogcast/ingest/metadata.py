from smogcast.ingest.gios import get_all_stations, get_station_sensors
from smogcast.storage.db import SessionLocal
from smogcast.storage.upsert import (
    map_sensor_from_gios,
    map_station_from_gios,
    upsert_metadata,
)


def ingest_metadata():
    gios_stations = get_all_stations()

    stations = []
    sensors = []

    for station in gios_stations:
        station_id = station["Identyfikator stacji"]

        stations.append(map_station_from_gios(station))

        station_sensors = get_station_sensors(station_id)

        for sensor in station_sensors:
            mapped_sensor = map_sensor_from_gios(
                sensor,
                station_id,
            )

            if mapped_sensor is not None:
                sensors.append(mapped_sensor)

    db = SessionLocal()

    try:
        upsert_metadata(
            db,
            stations,
            sensors,
        )
    finally:
        db.close()

    print(f"Saved {len(stations)} stations")
    print(f"Saved {len(sensors)} PM sensors")


if __name__ == "__main__":
    ingest_metadata()
