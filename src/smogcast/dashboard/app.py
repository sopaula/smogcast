import base64
import os
import time
from datetime import datetime, timedelta
from pathlib import Path

import altair as alt
import httpx
import pandas as pd
import pydeck as pdk
import streamlit as st


API_URL = os.getenv(
    "API_URL",
    "http://127.0.0.1:8000",
)

LOGO_PATH = Path(__file__).parent / "assets" / "logo.png"


# Przygotowuje logo do wyświetlenia w HTML.
def get_logo_base64():
    with open(LOGO_PATH, "rb") as logo_file:
        return base64.b64encode(logo_file.read()).decode()


logo_base64 = get_logo_base64()


THRESHOLDS = {
    "PM10": 50.0,
    "PM25": 25.0,
}


st.set_page_config(
    page_title="SmogCast",
    page_icon=str(LOGO_PATH),
    layout="wide",
)


# STYLE


st.markdown(
    """
<style>

header[data-testid="stHeader"] {
    display: none;
}

.block-container {
    padding-top: 95px;
    padding-bottom: 5rem;
    max-width: 1400px;
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

.top-bar {
    position: fixed;
    top: 0;
    left: 0;
    width: 100vw;
    height: 68px;
    z-index: 999999;

    display: flex;
    align-items: center;
    justify-content: space-between;

    padding: 0 40px;
    box-sizing: border-box;

    background-color: #f1f3f5;
    border-bottom: 1px solid #d9dde2;
    box-shadow: 0 2px 10px rgba(0, 0, 0, 0.08);
}

.top-bar-logo {
    display: flex;
    align-items: center;
    gap: 10px;

    font-size: 25px;
    font-weight: 700;
    color: #222;
}

.top-bar-logo-img {
    width: 38px;
    height: 38px;
    object-fit: contain;
}

.top-bar-subtitle {
    font-size: 14px;
    color: #666;
    font-weight: 400;
}

.source-bar {
    position: fixed;
    bottom: 0;
    left: 0;
    width: 100%;

    background-color: #f1f3f5;
    border-top: 1px solid #d9dde2;

    padding: 10px 20px;
    box-sizing: border-box;

    text-align: center;
    font-size: 13px;
    color: #666;

    z-index: 9999;
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


# Formatuje czas odświeżenia w polskiej strefie czasowej.
def format_refresh_timestamp(
    timestamp_text,
):
    timestamp = pd.to_datetime(
        timestamp_text,
        utc=True,
    )

    timestamp = timestamp.tz_convert(
        "Europe/Warsaw",
    )

    return timestamp.strftime("%d.%m.%Y, %H:%M")


# Formatuje datę.
def format_date(
    date_text,
):
    formatted_date = pd.to_datetime(date_text)

    return formatted_date.strftime("%d.%m.%Y")


# Zamienia techniczną nazwę parametru na nazwę wyświetlaną.
def display_param_name(
    param,
):
    if param == "PM25":
        return "PM2.5"

    return param


# Zamienia nazwę wyświetlaną na format używany przez backend.
def backend_param_name(
    param,
):
    if param == "PM2.5":
        return "PM25"

    return param


# API


# Ponawia żądanie przy chwilowym błędzie połączenia.
def get_with_retry(
    url,
    *,
    params=None,
    timeout=30.0,
    attempts=3,
):
    last_error = None

    for attempt in range(attempts):
        try:
            response = httpx.get(
                url,
                params=params,
                timeout=timeout,
            )
            response.raise_for_status()
            return response

        except httpx.HTTPError as error:
            last_error = error

            if attempt < attempts - 1:
                time.sleep(2)

    raise last_error


# Pobiera listę stacji.
@st.cache_data(ttl=60)
def get_stations():
    response = get_with_retry(
        f"{API_URL}/stations",
        timeout=30.0,
    )

    return response.json()


# Pobiera status ostatniego odświeżenia danych.
@st.cache_data(ttl=60)
def get_app_status():
    response = get_with_retry(
        f"{API_URL}/status",
        timeout=30.0,
    )

    return response.json()


# Pobiera najnowsze pomiary.
@st.cache_data(ttl=60)
def get_latest_measurements(
    station_id,
):
    response = get_with_retry(
        f"{API_URL}/stations/{station_id}/latest",
        timeout=30.0,
    )

    return response.json()


# Pobiera historię pomiarów.
@st.cache_data(ttl=60)
def get_measurements(
    station_id,
    param,
    days=None,
):
    params = {
        "param": param,
    }

    # Ogranicza historię do wybranego okresu.
    if days is not None:
        date_from = (datetime.now() - timedelta(days=days)).replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )

        params["date_from"] = date_from.isoformat()

    response = get_with_retry(
        f"{API_URL}/stations/{station_id}/measurements",
        params=params,
        timeout=30.0,
    )

    return response.json()


# Pobiera prognozę na jutro.
@st.cache_data(ttl=300)
def get_forecast(
    station_id,
):
    response = get_with_retry(
        f"{API_URL}/stations/{station_id}/forecast",
        timeout=60.0,
    )

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
    display_param = display_param_name(param)

    st.markdown(
        f"""
<div class="measurement-card {status["class"]}">
    <div class="card-param">{display_param}</div>
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
    display_param = display_param_name(param)

    st.markdown(
        f"""
<div class="measurement-card {status["class"]}">
    <div class="card-param">{display_param}</div>
    <div class="card-value">
        {value:.2f} µg/m³
    </div>
    <div class="card-status">
        {status["name"]}
    </div>
    <div class="card-info">
        Próg: {threshold:.0f} µg/m³<br>
        Dane do: {format_date(forecast["data_date"])}<br>
        Coverage 7 dni: {forecast["coverage_7d"]:.1f}%<br>
        Sensor: {forecast["sensor_id"]}
    </div>
</div>
        """,
        unsafe_allow_html=True,
    )

    if forecast["warning"]:
        st.warning(forecast["warning"])

    if forecast["coverage_status"] == "warning":
        st.warning(forecast["coverage_warning"])

    if forecast["coverage_status"] == "critical":
        st.error(forecast["coverage_warning"])


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
    f"""
<div class="top-bar">
    <div class="top-bar-logo">
        <img
            src="data:image/png;base64,{logo_base64}"
            class="top-bar-logo-img"
        >
        <span>SmogCast</span>
    </div>
    <div class="top-bar-subtitle">
        Monitoring i prognozowanie jakości powietrza w Polsce
    </div>
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


try:
    app_status = get_app_status()

except httpx.HTTPError:
    app_status = None


if not stations:
    st.warning("Brak dostępnych stacji.")

    st.stop()


if app_status is not None and app_status["last_successful_refresh"] is not None:
    last_refresh = format_refresh_timestamp(
        app_status["last_successful_refresh"],
    )

    st.caption(f"Ostatnia udana aktualizacja danych: {last_refresh}")


# MAPA


st.markdown(
    '<div class="section-title">Mapa jakości powietrza</div>',
    unsafe_allow_html=True,
)


map_param_display = st.radio(
    "Wyświetlany parametr",
    [
        "PM10",
        "PM2.5",
    ],
    horizontal=True,
)


map_param = backend_param_name(map_param_display)


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
        get_radius=10000,
        pickable=True,
    )

    # Ustawia widok mapy na Polskę.
    view_state = pdk.ViewState(
        latitude=52.0,
        longitude=19.0,
        zoom=5.8,
        min_zoom=5.2,
        max_zoom=10,
    )

    tooltip = {
        "html": (
            "<b>{city}</b><br/>"
            "{name}<br/><br/>"
            f"{map_param_display}: "
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
    (f"{station['city']} — {station['name']}"): station["id"] for station in stations
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

except httpx.HTTPError as exc:
    forecast = None

    st.warning("Nie udało się pobrać prognozy.")

    st.caption(str(exc))


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


history_param_display = st.radio(
    "Wyświetlany parametr",
    [
        "PM10",
        "PM2.5",
    ],
    horizontal=True,
    key="history_param",
)


history_param = backend_param_name(history_param_display)


history_range = st.selectbox(
    "Zakres danych",
    [
        "7 dni",
        "30 dni",
        "90 dni",
        "1 rok",
    ],
)


history_days = {
    "7 dni": 7,
    "30 dni": 30,
    "90 dni": 90,
    "1 rok": 365,
}


try:
    history = get_measurements(
        station_id,
        history_param,
        history_days[history_range],
    )

except httpx.HTTPError:
    history = []

    st.error("Nie udało się pobrać historii pomiarów.")


if history:
    history_df = pd.DataFrame(history)

    history_df["timestamp"] = pd.to_datetime(
        history_df["timestamp"],
        utc=True,
    )

    history_df = history_df.sort_values("timestamp")

    chart_name = history_param_display

    polish_months = {
        1: "Sty",
        2: "Lut",
        3: "Mar",
        4: "Kwi",
        5: "Maj",
        6: "Cze",
        7: "Lip",
        8: "Sie",
        9: "Wrz",
        10: "Paź",
        11: "Lis",
        12: "Gru",
    }

    today = pd.Timestamp.now(tz="UTC").normalize()

    # Ustawia początek zakresu.
    date_from = today - pd.Timedelta(days=history_days[history_range])

    date_to = today + pd.Timedelta(days=1)

    history_df = history_df[
        (history_df["timestamp"] >= date_from) & (history_df["timestamp"] < date_to)
    ].copy()

    # Przygotowuje polską datę do tooltipa.
    history_df["data_tooltip"] = history_df["timestamp"].apply(
        lambda value: (
            f"{value.day} {polish_months[value.month]}, {value.strftime('%H:%M')}"
        )
    )

    # Ustawia daty na osi.
    if history_range == "7 dni":
        tick_dates = pd.date_range(
            start=date_from,
            end=today,
            freq="1D",
        )

    elif history_range == "30 dni":
        tick_dates = pd.date_range(
            start=date_from,
            end=today,
            freq="7D",
        )

    elif history_range == "90 dni":
        tick_dates = pd.date_range(
            start=date_from,
            end=today,
            freq="14D",
        )

    else:
        tick_dates = pd.date_range(
            start=date_from,
            end=today,
            freq="MS",
        )

    tick_dates = tick_dates.to_pydatetime().tolist()

    # Ustawia format etykiet osi.
    if history_range == "1 rok":
        axis = alt.Axis(
            values=tick_dates,
            labelExpr=(
                "['Sty', 'Lut', 'Mar', 'Kwi', "
                "'Maj', 'Cze', 'Lip', 'Sie', "
                "'Wrz', 'Paź', 'Lis', 'Gru']"
                "[month(datum.value)] + ' ' + "
                "year(datum.value)"
            ),
            labelAngle=0,
        )

    else:
        axis = alt.Axis(
            values=tick_dates,
            labelExpr=(
                "date(datum.value) + ' ' + "
                "['Sty', 'Lut', 'Mar', 'Kwi', "
                "'Maj', 'Cze', 'Lip', 'Sie', "
                "'Wrz', 'Paź', 'Lis', 'Gru']"
                "[month(datum.value)]"
            ),
            labelAngle=0,
        )

    # Bazowy wykres.
    base = alt.Chart(history_df).encode(
        x=alt.X(
            "timestamp:T",
            title="Data",
            scale=alt.Scale(
                domain=[
                    date_from.to_pydatetime(),
                    date_to.to_pydatetime(),
                ]
            ),
            axis=axis,
        ),
        y=alt.Y(
            "value:Q",
            title="Stężenie [µg/m³]",
        ),
    )

    # Wybiera najbliższy punkt.
    nearest = alt.selection_point(
        nearest=True,
        on="pointerover",
        fields=[
            "timestamp",
        ],
        empty=False,
    )

    # Linia pomiarów.
    line = base.mark_line(
        tooltip=None,
    )

    selectors = base.mark_point(
        opacity=0,
        tooltip=None,
    ).add_params(nearest)

    # Pokazuje kulkę przy wybranym punkcie.
    points = base.mark_point(
        size=80,
    ).encode(
        opacity=alt.condition(
            nearest,
            alt.value(1),
            alt.value(0),
        ),
        tooltip=[
            alt.Tooltip(
                "data_tooltip:N",
                title="Data",
            ),
            alt.Tooltip(
                "value:Q",
                title=chart_name,
                format=".2f",
            ),
        ],
    )

    # Pokazuje pionową linię.
    rules = (
        alt.Chart(history_df)
        .mark_rule(
            tooltip=None,
        )
        .encode(
            x="timestamp:T",
            opacity=alt.condition(
                nearest,
                alt.value(0.3),
                alt.value(0),
            ),
        )
        .transform_filter(nearest)
    )

    chart = alt.layer(
        line,
        selectors,
        points,
        rules,
    ).properties(height=350)

    st.altair_chart(
        chart,
        use_container_width=True,
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
