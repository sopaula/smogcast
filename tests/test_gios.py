import json
from pathlib import Path

from smogcast.ingest.gios import parse_stations


def test_parse_stations():
    fixture_path = Path(__file__).parent / "fixtures" / "stations.json"

    with fixture_path.open(encoding="utf-8") as file:
        data = json.load(file)

    stations = parse_stations(data)

    assert len(stations) == 2
    assert stations[0]["Identyfikator stacji"] == 11
    assert stations[0]["Nazwa stacji"] == "Czerniawa"
