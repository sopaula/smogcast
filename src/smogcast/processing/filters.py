def filter_silesian_stations(stations):
    return [station for station in stations if station["Województwo"] == "ŚLĄSKIE"]
