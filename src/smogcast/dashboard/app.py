import httpx
import pandas as pd
import pydeck as pdk
import streamlit as st


API_URL = "http://127.0.0.1:8000"


THRESHOLDS = {
    "PM10": 50.0,
    "PM25": 25.0,
}


st.set_page_config(
    page_title="Smogcast",
    page_icon="☁️",
    layout="wide",
)


# STYLE


st.markdown(
    """
    <style>
    .block-container {
        padding-top: 2rem;
        padding-bottom: 5rem;
        max-width: 1400px;
    }

    .main-title {
        font-size: 42px;
        font-weight: 700;
        margin-bottom: 0;
    }

    .subtitle {
        color: #666;
        font-size: 18px;
        margin-top: 0;
        margin-bottom: 25px;
    }

    .section-title {
        font-size: 26px;
        font-weight: 600;
        margin-top: 30px;
        margin-bottom: 15px;
    }

    .measurement-card {
        padding: 22px;
        border-radius: 16px;
        border: 1px solid rgba(0, 0, 0, 0.08);
        min-height: 190px;
    }

    .card-green {
        background-color: rgba(46, 204, 113, 0.13);
        border-left: 6px solid #2ecc71;
    }

    .card-yellow {
        background-color: rgba(241, 196, 15, 0.16);
        border-left: 6px solid #f1c40f;
    }

    .card-red {
        background-color: rgba(231, 76, 60, 0.13);
        border-left: 6px solid #e74c3c;
    }

    .card-param {
        font-size: 18px;
        font-weight: 600;
        color: #444;
    }

    .card-value {
        font-size: 34px;
        font-weight: 700;
        margin-top: 8px;
        margin-bottom: 8px;
    }

    .card-status {
        font-size: 15px;
        font-weight: 600;
        margin-bottom: 12px;
    }

    .card-info {
        font-size: 13px;
        color: #666;
        line-height: 1.6;
    }

    .source-bar {
        position: fixed;
        bottom: 0;
        left: 0;
        width: 100%;
        background-color: white;
        border-top: 1px solid #ddd;
        padding: 10px 20px;
        text-align: center;
        font-size: 13px;
        color: #666;
        z-index: 9999;
    }

    .legend {
        display: flex;
        gap: 20px;
        margin-top: 8px;
        margin-bottom: 10px;
        font-size: 14px;
    }

    .legend-item {
        display: flex;
        align-items: center;
        gap: 7px;
    }

    .legend-dot {
        width: 12px;
        height: 12px;
        border-radius: 50%;
        display: inline-block;
    }

    .dot-green {
        background-color: #2ecc71;
    }

    .dot-yellow {
        background-color: #f1c40f;
    }

    .dot-red {
        background-color: #e74c3c;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# FORMATOWANIE


# Formatuje datę i godzinę.
def format_timestamp(
    timestamp_text,
):
    timestamp = pd.to_datetime(timestamp_text)

    return timestamp.strftime("%d.%m.%Y, %H:%M")


# Formatuje datę.
def format_date(
    date_text,
):
    formatted_date = pd.to_datetime(date_text)

    return formatted_date.strftime("%d.%m.%Y")


# API


# Pobiera listę stacji.
@st.cache_data(ttl=60)
def get_stations():
    response = httpx.get(
        f"{API_URL}/stations",
        timeout=10.0,
    )

    response.raise_for_status()

    return response.json()


# Pobiera najnowsze pomiary.
@st.cache_data(ttl=60)
def get_latest_measurements(
    station_id,
):
    response = httpx.get(
        f"{API_URL}/stations/{station_id}/latest",
        timeout=10.0,
    )

    response.raise_for_status()

    return response.json()


# Pobiera historię pomiarów.
@st.cache_data(ttl=60)
def get_measurements(
    station_id,
    param,
):
    response = httpx.get(
        f"{API_URL}/stations/{station_id}/measurements",
        params={
            "param": param,
        },
        timeout=20.0,
    )

    response.raise_for_status()

    return response.json()


# Pobiera prognozę na jutro.
@st.cache_data(ttl=300)
def get_forecast(
    station_id,
):
    response = httpx.get(
        f"{API_URL}/stations/{station_id}/forecast",
        timeout=30.0,
    )

    response.raise_for_status()

    return response.json()


# STATUS I KOLORY


# Określa poziom względem progu.
def get_status(
    value,
    param,
):
    threshold = THRESHOLDS[param]

    warning_level = threshold * 0.8

    if value > threshold:
        return {
            "name": "Przekroczenie progu",
            "class": "card-red",
        }

    if value >= warning_level:
        return {
            "name": "Wartość zbliżona do progu",
            "class": "card-yellow",
        }

    return {
        "name": "Poziom poniżej progu",
        "class": "card-green",
    }


# Ustawia kolor punktu na mapie.
def get_pollutant_color(
    value,
    param,
):
    if value is None:
        return [
            128,
            128,
            128,
        ]

    threshold = THRESHOLDS[param]

    warning_level = threshold * 0.8

    if value > threshold:
        return [
            220,
            0,
            0,
        ]

    if value >= warning_level:
        return [
            255,
            200,
            0,
        ]

    return [
        0,
        180,
        0,
    ]


# KARTY


# Wyświetla kartę pomiaru.
def show_measurement_card(
    param,
    value,
    sensor_id,
    timestamp,
):
    status = get_status(
        value,
        param,
    )

    threshold = THRESHOLDS[param]

    st.markdown(
        f"""
        <div class="measurement-card {status["class"]}">
            <div class="card-param">{param}</div>
            <div class="card-value">
                {value:.2f} µg/m³
            </div>
            <div class="card-status">
                {status["name"]}
            </div>
            <div class="card-info">
                Próg: {threshold:.0f} µg/m³<br>
                Pomiar: {format_timestamp(timestamp)}<br>
                Sensor: {sensor_id}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# Wyświetla kartę prognozy.
def show_forecast_card(
    param,
    forecast,
):
    value = forecast["forecast_value"]

    status = get_status(
        value,
        param,
    )

    threshold = forecast["threshold"]

    st.markdown(
        f"""
        <div class="measurement-card {status["class"]}">
            <div class="card-param">{param}</div>
            <div class="card-value">
                {value:.2f} µg/m³
            </div>
            <div class="card-status">
                {status["name"]}
            </div>
            <div class="card-info">
                Próg: {threshold:.0f} µg/m³<br>
                Dane do: {format_date(forecast["data_date"])}<br>
                Sensor: {forecast["sensor_id"]}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if forecast["warning"]:
        st.warning(forecast["warning"])


# MAPA


# Pobiera pomiar wybranego parametru.
def get_latest_pollutant(
    station_id,
    param,
):
    measurements = get_latest_measurements(station_id)

    for measurement in measurements:
        if measurement["param"] == param:
            return measurement

    return None


# Przygotowuje dane do mapy.
def prepare_map_data(
    stations,
    param,
):
    map_data = []

    for station in stations:
        try:
            latest_measurement = get_latest_pollutant(
                station["id"],
                param,
            )

        except httpx.HTTPError:
            continue

        if latest_measurement is None:
            continue

        value = latest_measurement["value"]

        map_data.append(
            {
                "station_id": station["id"],
                "name": station["name"],
                "city": station["city"],
                "lat": station["latitude"],
                "lon": station["longitude"],
                "value": value,
                "timestamp": format_timestamp(latest_measurement["timestamp"]),
                "color": get_pollutant_color(
                    value,
                    param,
                ),
            }
        )

    return map_data


# NAGŁÓWEK


st.markdown(
    """
    <div class="main-title">Smogcast</div>
    <div class="subtitle">
        Monitoring i prognozowanie jakości powietrza w Polsce
    </div>
    """,
    unsafe_allow_html=True,
)


# STACJE


try:
    stations = get_stations()

except httpx.HTTPError:
    st.error("Nie udało się połączyć z API.")

    st.stop()


if not stations:
    st.warning("Brak dostępnych stacji.")

    st.stop()


# MAPA


st.markdown(
    '<div class="section-title">Mapa jakości powietrza</div>',
    unsafe_allow_html=True,
)


map_param = st.radio(
    "Wyświetlany parametr",
    [
        "PM10",
        "PM25",
    ],
    horizontal=True,
)


map_data = prepare_map_data(
    stations,
    map_param,
)


if map_data:
    layer = pdk.Layer(
        "ScatterplotLayer",
        data=map_data,
        get_position="[lon, lat]",
        get_fill_color="color",
        get_radius=12000,
        pickable=True,
    )

    view_state = pdk.ViewState(
        latitude=52.0,
        longitude=19.0,
        zoom=5.5,
    )

    tooltip = {
        "html": (
            "<b>{city}</b><br/>"
            "{name}<br/><br/>"
            f"{map_param}: "
            "<b>{value} µg/m³</b><br/>"
            "Pomiar: {timestamp}"
        )
    }

    deck = pdk.Deck(
        layers=[
            layer,
        ],
        initial_view_state=view_state,
        tooltip=tooltip,
    )

    st.pydeck_chart(
        deck,
        use_container_width=True,
    )

    st.markdown(
        """
        <div class="legend">
            <div class="legend-item">
                <span class="legend-dot dot-green"></span>
                poniżej 80% progu
            </div>
            <div class="legend-item">
                <span class="legend-dot dot-yellow"></span>
                blisko progu
            </div>
            <div class="legend-item">
                <span class="legend-dot dot-red"></span>
                przekroczenie progu
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

else:
    st.info("Brak danych do wyświetlenia na mapie.")


# WYBÓR STACJI


st.markdown(
    '<div class="section-title">Szczegóły stacji</div>',
    unsafe_allow_html=True,
)


station_options = {
    f"{station['city']} — {station['name']}": station["id"] for station in stations
}


selected_station = st.selectbox(
    "Wybierz stację",
    station_options.keys(),
)


station_id = station_options[selected_station]


# NAJNOWSZE POMIARY


st.markdown(
    '<div class="section-title">Najnowsze pomiary</div>',
    unsafe_allow_html=True,
)


try:
    latest = get_latest_measurements(station_id)

except httpx.HTTPError:
    latest = []

    st.error("Nie udało się pobrać najnowszych pomiarów.")


latest_by_param = {measurement["param"]: measurement for measurement in latest}


col1, col2 = st.columns(2)


with col1:
    pm10 = latest_by_param.get("PM10")

    if pm10 is not None:
        show_measurement_card(
            param="PM10",
            value=pm10["value"],
            sensor_id=pm10["sensor_id"],
            timestamp=pm10["timestamp"],
        )

    else:
        st.info("Brak pomiaru PM10.")


with col2:
    pm25 = latest_by_param.get("PM25")

    if pm25 is not None:
        show_measurement_card(
            param="PM25",
            value=pm25["value"],
            sensor_id=pm25["sensor_id"],
            timestamp=pm25["timestamp"],
        )

    else:
        st.info("Brak pomiaru PM2.5.")


# PROGNOZA


st.markdown(
    '<div class="section-title">Prognoza na jutro</div>',
    unsafe_allow_html=True,
)


try:
    forecast = get_forecast(station_id)

except httpx.HTTPError:
    forecast = None

    st.error("Nie udało się pobrać prognozy.")


if forecast is not None:
    st.caption(f"Prognoza dla {format_date(forecast['forecast_date'])}")

    col1, col2 = st.columns(2)

    with col1:
        show_forecast_card(
            "PM10",
            forecast["pm10"],
        )

    with col2:
        show_forecast_card(
            "PM25",
            forecast["pm25"],
        )


# HISTORIA


st.markdown(
    '<div class="section-title">Historia pomiarów</div>',
    unsafe_allow_html=True,
)


try:
    pm10_history = get_measurements(
        station_id,
        "PM10",
    )

    pm25_history = get_measurements(
        station_id,
        "PM25",
    )

except httpx.HTTPError:
    pm10_history = []
    pm25_history = []

    st.error("Nie udało się pobrać historii pomiarów.")


history_records = []


for measurement in pm10_history:
    history_records.append(
        {
            "timestamp": measurement["timestamp"],
            "PM10": measurement["value"],
            "PM2.5": None,
        }
    )


for measurement in pm25_history:
    history_records.append(
        {
            "timestamp": measurement["timestamp"],
            "PM10": None,
            "PM2.5": measurement["value"],
        }
    )


if history_records:
    history_df = pd.DataFrame(history_records)

    history_df["timestamp"] = pd.to_datetime(history_df["timestamp"])

    history_df = history_df.groupby("timestamp").first().sort_index()

    st.line_chart(
        history_df[
            [
                "PM10",
                "PM2.5",
            ]
        ],
        x_label="Data",
        y_label="Stężenie [µg/m³]",
        height=350,
    )

else:
    st.info("Brak historii pomiarów.")


# STAŁY PASEK ŹRÓDEŁ


st.markdown(
    """
    <div class="source-bar">
        Dane o jakości powietrza:
        <b>Główny Inspektorat Ochrony Środowiska (GIOŚ)</b>
        &nbsp;&nbsp;|&nbsp;&nbsp;
        Dane meteorologiczne:
        <b>Open-Meteo</b>
    </div>
    """,
    unsafe_allow_html=True,
)
