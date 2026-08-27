import httpx

STATIONS_URL = "https://api.gios.gov.pl/pjp-api/v1/rest/station/findAll"


def parse_stations(data):
    return data["Lista stacji pomiarowych"]


def get_all_stations():
    stations = []

    response = httpx.get(STATIONS_URL, timeout=10.0)
    response.raise_for_status()
    data = response.json()

    stations.extend(parse_stations(data))

    total_pages = data["totalPages"]

    for page in range(1, total_pages):
        response = httpx.get(
            STATIONS_URL,
            params={"page": page, "size": 20},
            timeout=10.0,
        )
        response.raise_for_status()

        page_data = response.json()
        stations.extend(parse_stations(page_data))

    return stations
