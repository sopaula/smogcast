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


# Przygotowuje logo do wyświetlenia.
def get_logo_base64():
    with open(LOGO_PATH, "rb") as logo_file:
        return base64.b64encode(logo_file.read()).decode()


logo_base64 = get_logo_base64()


# Progi Polskiego Indeksu Jakości Powietrza.
AIR_QUALITY_LEVELS = {
    "PM10": [
        (20.0, "Bardzo dobry", "card-very-good", [0, 180, 0]),
        (50.0, "Dobry", "card-good", [100, 200, 0]),
        (80.0, "Umiarkowany", "card-moderate", [255, 200, 0]),
        (110.0, "Dostateczny", "card-sufficient", [255, 140, 0]),
        (150.0, "Zły", "card-bad", [220, 0, 0]),
    ],
    "PM25": [
        (13.0, "Bardzo dobry", "card-very-good", [0, 180, 0]),
        (35.0, "Dobry", "card-good", [100, 200, 0]),
        (55.0, "Umiarkowany", "card-moderate", [255, 200, 0]),
        (75.0, "Dostateczny", "card-sufficient", [255, 140, 0]),
        (110.0, "Zły", "card-bad", [220, 0, 0]),
    ],
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
    background: transparent;
    height: 0;
}

header[data-testid="stHeader"] > div {
    background: transparent;
}

div[data-testid="stToolbar"] {
    z-index: 1000;
}

button[data-testid="stDeployButton"] {
    display: none;
}

div[data-testid="stToolbarActions"] > div:not(:last-child) {
    display: none;
}

div[data-testid="stToolbar"] button,
div[data-testid="stToolbar"] svg {
    color: var(--text-color) !important;
    fill: var(--text-color) !important;
}

.block-container {
    padding-top: 92px;
    padding-bottom: 3rem;
    padding-left: 2.5rem;
    padding-right: 2.5rem;
    max-width: 1700px;
}

.section-title {
    font-size: 28px;
    font-weight: 700;
    margin-top: 20px;
    margin-bottom: 12px;
}

.section-subtitle {
    font-size: 15px;
    opacity: 0.65;
    margin-top: -4px;
    margin-bottom: 14px;
}

.measurement-card,
.forecast-card {
    padding: 22px 24px;
    border-radius: 14px;
    border: 1px solid rgba(128, 128, 128, 0.22);
    box-sizing: border-box;
    min-height: 180px;
}

.card-very-good {
    background-color: rgba(0, 180, 0, 0.11);
    border-left: 6px solid rgb(0, 180, 0);
}

.card-good {
    background-color: rgba(100, 200, 0, 0.12);
    border-left: 6px solid rgb(100, 200, 0);
}

.card-moderate {
    background-color: rgba(255, 200, 0, 0.15);
    border-left: 6px solid rgb(255, 200, 0);
}

.card-sufficient {
    background-color: rgba(255, 140, 0, 0.14);
    border-left: 6px solid rgb(255, 140, 0);
}

.card-bad {
    background-color: rgba(220, 0, 0, 0.11);
    border-left: 6px solid rgb(220, 0, 0);
}

.card-very-bad {
    background-color: rgba(140, 0, 0, 0.14);
    border-left: 6px solid rgb(140, 0, 0);
}

.card-label {
    font-size: 13px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    opacity: 0.65;
    margin-bottom: 6px;
}

.card-param {
    font-size: 18px;
    font-weight: 650;
}

.card-value {
    font-size: 36px;
    font-weight: 750;
    margin-top: 7px;
    margin-bottom: 5px;
}

.card-status {
    font-size: 16px;
    font-weight: 650;
    margin-bottom: 9px;
}

.card-info {
    font-size: 14px;
    line-height: 1.55;
    opacity: 0.72;
}

.map-note {
    font-size: 14px;
    opacity: 0.68;
    margin-top: -3px;
    margin-bottom: 8px;
}

.legend {
    display: flex;
    flex-wrap: wrap;
    gap: 14px;
    margin-top: 8px;
    margin-bottom: 8px;
    font-size: 13px;
}

.legend-item {
    display: flex;
    align-items: center;
    gap: 6px;
}

.legend-dot {
    width: 11px;
    height: 11px;
    border-radius: 50%;
    display: inline-block;
}

.dot-very-good {
    background-color: rgb(0, 180, 0);
}

.dot-good {
    background-color: rgb(100, 200, 0);
}

.dot-moderate {
    background-color: rgb(255, 200, 0);
}

.dot-sufficient {
    background-color: rgb(255, 140, 0);
}

.dot-bad {
    background-color: rgb(220, 0, 0);
}

.dot-very-bad {
    background-color: rgb(140, 0, 0);
}

.top-bar {
    position: fixed;
    top: 0;
    left: 0;
    width: 100vw;
    height: 68px;
    z-index: 999;

    display: flex;
    align-items: center;
    justify-content: space-between;

    padding: 0 140px 0 40px;
    box-sizing: border-box;

    background-color: #0e1117 !important;
    opacity: 1 !important;

    border-bottom: 1px solid #262730;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.25);
}

.top-bar-logo {
    display: flex;
    align-items: center;
    gap: 10px;

    font-size: 25px;
    font-weight: 700;
    color: #f5f5f5;
}

.top-bar-logo-img {
    width: 38px;
    height: 38px;
    object-fit: contain;
}

.top-bar-subtitle {
    font-size: 14px;
    color: #f5f5f5;
    opacity: 0.68;
    font-weight: 400;
}

div[data-testid="stExpander"] {
    border: 1px solid rgba(128, 128, 128, 0.22);
    border-radius: 12px;
    overflow: hidden;
}

div[data-testid="stExpander"] details summary {
    padding-top: 6px;
    padding-bottom: 6px;
}

.chart-header {
    margin-top: 8px;
    margin-bottom: 20px;
}

.chart-title {
    font-size: 27px;
    font-weight: 700;
    margin-bottom: 5px;
}

.chart-subtitle {
    font-size: 15px;
    opacity: 0.65;
}

.summary-card {
    padding: 16px 18px;
    border-radius: 12px;
    background: rgba(128, 128, 128, 0.07);
    border: 1px solid rgba(128, 128, 128, 0.16);
    min-height: 92px;
}

.summary-label {
    font-size: 13px;
    opacity: 0.65;
    margin-bottom: 7px;
}

.summary-value {
    font-size: 27px;
    font-weight: 700;
}

.source-footer {
    margin-top: 40px;
    padding-top: 18px;
    padding-bottom: 12px;
    border-top: 1px solid rgba(128, 128, 128, 0.2);
    text-align: center;
    font-size: 15px;
    line-height: 1.6;
    opacity: 0.78;
}

@media (prefers-color-scheme: light) {
    .top-bar {
        background-color: #ffffff !important;
        border-bottom: 1px solid #d9dde2;
        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.08);
    }

    .top-bar-logo,
    .top-bar-subtitle {
        color: #222222 !important;
    }
}

@media (max-width: 768px) {
    .block-container {
        padding-top: 105px;
        padding-left: 1rem;
        padding-right: 1rem;
        padding-bottom: 2rem;
        max-width: 100%;
    }

    .top-bar {
        height: auto;
        min-height: 78px;
        padding: 10px 55px 10px 14px;
        gap: 8px;
        flex-wrap: wrap;
    }

    .top-bar-logo {
        font-size: 20px;
        gap: 8px;
    }

    .top-bar-logo-img {
        width: 30px;
        height: 30px;
    }

    .top-bar-subtitle {
        font-size: 11px;
        line-height: 1.3;
        max-width: 160px;
        text-align: right;
    }

    .section-title {
        font-size: 22px;
    }

    .measurement-card,
    .forecast-card {
        min-height: auto;
        padding: 16px;
    }

    .card-param {
        font-size: 16px;
    }

    .card-value {
        font-size: 28px;
    }

    .card-status {
        font-size: 14px;
    }

    .card-info {
        font-size: 13px;
    }

    .legend {
        gap: 9px;
        font-size: 11px;
    }

    .summary-value {
        font-size: 22px;
    }

    .source-footer {
        font-size: 12px;
    }
}

</style>
    """,
    unsafe_allow_html=True,
)


# FORMATOWANIE


# Formatuje datę i godzinę.
def format_timestamp(timestamp_text):
    timestamp = pd.to_datetime(
        timestamp_text,
        utc=True,
    )

    timestamp = timestamp.tz_convert("Europe/Warsaw")

    return timestamp.strftime("%d.%m.%Y, %H:%M")


# Formatuje czas odświeżenia.
def format_refresh_timestamp(timestamp_text):
    timestamp = pd.to_datetime(
        timestamp_text,
        utc=True,
    )

    timestamp = timestamp.tz_convert("Europe/Warsaw")

    return timestamp.strftime("%d.%m.%Y, %H:%M")


# Formatuje datę.
def format_date(date_text):
    formatted_date = pd.to_datetime(date_text)

    return formatted_date.strftime("%d.%m.%Y")


# Zwraca wiek pomiaru.
def get_measurement_age(timestamp_text):
    timestamp = pd.to_datetime(
        timestamp_text,
        utc=True,
    )

    now = pd.Timestamp.now(tz="UTC")
    age = now - timestamp

    total_hours = max(
        0,
        int(age.total_seconds() // 3600),
    )

    if total_hours < 1:
        return "mniej niż godzinę temu"

    if total_hours < 24:
        return f"{total_hours} godz. temu"

    days = total_hours // 24

    if days == 1:
        return "1 dzień temu"

    return f"{days} dni temu"


# Sprawdza, czy pomiar jest stary.
def is_stale_measurement(timestamp_text):
    timestamp = pd.to_datetime(
        timestamp_text,
        utc=True,
    )

    age = pd.Timestamp.now(tz="UTC") - timestamp

    return age > pd.Timedelta(days=2)


# Zamienia nazwę parametru na nazwę wyświetlaną.
def display_param_name(param):
    if param == "PM25":
        return "PM2.5"

    return param


# Zamienia nazwę wyświetlaną na format backendu.
def backend_param_name(param):
    if param == "PM2.5":
        return "PM25"

    return param


# API


# Ponawia żądanie przy chwilowym błędzie.
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


# Pobiera status ostatniego odświeżenia.
@st.cache_data(ttl=60)
def get_app_status():
    response = get_with_retry(
        f"{API_URL}/status",
        timeout=30.0,
    )

    return response.json()


# Pobiera najnowsze pomiary.
@st.cache_data(ttl=60)
def get_latest_measurements(station_id):
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

    if days is not None:
        date_from = (datetime.now() - timedelta(days=days)).replace(
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
def get_forecast(station_id):
    response = get_with_retry(
        f"{API_URL}/stations/{station_id}/forecast",
        timeout=60.0,
    )

    return response.json()


# STATUS I KOLORY


# Określa kategorię jakości powietrza.
def get_status(
    value,
    param,
):
    for threshold, name, card_class, color in AIR_QUALITY_LEVELS[param]:
        if value <= threshold:
            return {
                "name": name,
                "class": card_class,
                "color": color,
            }

    return {
        "name": "Bardzo zły",
        "class": "card-very-bad",
        "color": [140, 0, 0],
    }


# KARTY


# Wyświetla kartę pomiaru.
def show_measurement_card(
    param,
    value,
    timestamp,
):
    status = get_status(
        value,
        param,
    )

    display_param = display_param_name(param)

    st.markdown(
        f"""
<div class="measurement-card {status["class"]}">
    <div class="card-label">Ostatni pomiar</div>
    <div class="card-param">{display_param}</div>
    <div class="card-value">{value:.2f} µg/m³</div>
    <div class="card-status">{status["name"]}</div>
    <div class="card-info">
        {format_timestamp(timestamp)}<br>
        {get_measurement_age(timestamp)}
    </div>
</div>
        """,
        unsafe_allow_html=True,
    )


# Wyświetla kartę prognozy.
def show_forecast_card(
    param,
    forecast,
    forecast_date,
):
    value = forecast["forecast_value"]

    status = get_status(
        value,
        param,
    )

    display_param = display_param_name(param)

    st.markdown(
        f"""
<div class="forecast-card {status["class"]}">
    <div class="card-label">Prognoza na jutro</div>
    <div class="card-param">{display_param}</div>
    <div class="card-value">{value:.2f} µg/m³</div>
    <div class="card-status">{status["name"]}</div>
    <div class="card-info">
        Prognozowana średnia dobowa<br>
        {format_date(forecast_date)}
    </div>
</div>
        """,
        unsafe_allow_html=True,
    )


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

        if value is None:
            continue

        status = get_status(
            value,
            param,
        )

        map_data.append(
            {
                "station_id": station["id"],
                "name": station["name"],
                "city": station["city"],
                "lat": station["latitude"],
                "lon": station["longitude"],
                "value": round(value, 2),
                "age": get_measurement_age(
                    latest_measurement["timestamp"],
                ),
                "timestamp": format_timestamp(
                    latest_measurement["timestamp"],
                ),
                "status": status["name"],
                "color": status["color"],
            }
        )

    return map_data


# WYKRES


# Przygotowuje historię dla wybranego zakresu.
def prepare_history_data(
    history,
    days,
):
    history_df = pd.DataFrame(history)

    if history_df.empty:
        return history_df, None

    history_df["timestamp"] = pd.to_datetime(
        history_df["timestamp"],
        utc=True,
    )

    history_df["value"] = pd.to_numeric(
        history_df["value"],
        errors="coerce",
    )

    history_df = history_df.sort_values("timestamp")

    now = pd.Timestamp.now(tz="UTC").floor("h")
    date_from = now - pd.Timedelta(days=days)

    history_df = history_df[
        (history_df["timestamp"] >= date_from) & (history_df["timestamp"] <= now)
    ].copy()

    if history_df.empty:
        return history_df, None

    hourly = history_df.set_index("timestamp")["value"].resample("1h").mean()

    full_index = pd.date_range(
        start=date_from,
        end=now,
        freq="1h",
        tz="UTC",
    )

    hourly = hourly.reindex(full_index)

    completeness = hourly.notna().mean() * 100

    hourly_df = hourly.rename("value").reset_index()

    hourly_df = hourly_df.rename(
        columns={
            "index": "timestamp",
        }
    )

    # Przy dłuższych zakresach używa średnich dobowych.
    if days >= 90:
        chart_df = (
            hourly_df.set_index("timestamp")["value"]
            .resample("1D")
            .mean()
            .reset_index()
        )

    else:
        chart_df = hourly_df

    return chart_df, completeness


# Przygotowuje etykiety osi czasu.
def get_chart_axis(
    history_range,
    date_from,
    date_to,
):
    polish_months = (
        "['Sty', 'Lut', 'Mar', 'Kwi', "
        "'Maj', 'Cze', 'Lip', 'Sie', "
        "'Wrz', 'Paź', 'Lis', 'Gru']"
    )

    if history_range == "7 dni":
        tick_dates = pd.date_range(
            start=date_from,
            end=date_to,
            freq="1D",
        )

    elif history_range == "30 dni":
        tick_dates = pd.date_range(
            start=date_from,
            end=date_to,
            freq="7D",
        )

    elif history_range == "90 dni":
        tick_dates = pd.date_range(
            start=date_from,
            end=date_to,
            freq="14D",
        )

    else:
        tick_dates = pd.date_range(
            start=date_from,
            end=date_to,
            freq="MS",
        )

    values = tick_dates.to_pydatetime().tolist()

    if history_range == "1 rok":
        return alt.Axis(
            values=values,
            labelExpr=(
                f"{polish_months}[month(datum.value)] + ' ' + year(datum.value)"
            ),
            labelAngle=-35,
            title="Data",
        )

    return alt.Axis(
        values=values,
        labelExpr=(f"date(datum.value) + ' ' + {polish_months}[month(datum.value)]"),
        labelAngle=-35,
        title="Data",
    )


# NAGŁÓWEK


st.markdown(
    f"""
<div class="top-bar">
    <div class="top-bar-logo">
        <img src="data:image/png;base64,{logo_base64}" class="top-bar-logo-img">
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
    st.error("Nie udało się połączyć z API. Spróbuj ponownie za chwilę.")

    st.stop()


if not stations:
    st.warning("Brak dostępnych stacji.")
    st.stop()


try:
    app_status = get_app_status()

except httpx.HTTPError:
    app_status = None


station_options = {
    f"{station['city']} — {station['name']}": station["id"] for station in stations
}

station_labels = list(station_options.keys())

station_label_by_id = {
    station_id: label for label, station_id in station_options.items()
}


if "pending_station_id" in st.session_state:
    pending_station_id = st.session_state.pop("pending_station_id")

    if pending_station_id in station_label_by_id:
        st.session_state.selected_station_id = pending_station_id
        st.session_state.station_selector = station_label_by_id[pending_station_id]


if "selected_station_id" not in st.session_state:
    st.session_state.selected_station_id = stations[0]["id"]


if st.session_state.selected_station_id not in station_label_by_id:
    st.session_state.selected_station_id = stations[0]["id"]


if "station_selector" not in st.session_state:
    st.session_state.station_selector = station_label_by_id[
        st.session_state.selected_station_id
    ]


# Synchronizuje listę ze stacją.
def update_station_from_selectbox():
    selected_label = st.session_state.station_selector

    st.session_state.selected_station_id = station_options[selected_label]


st.markdown(
    '<div class="section-title">Wybierz stację</div>',
    unsafe_allow_html=True,
)


st.selectbox(
    "Stacja pomiarowa",
    station_labels,
    key="station_selector",
    on_change=update_station_from_selectbox,
    label_visibility="collapsed",
)


station_id = st.session_state.selected_station_id
selected_station = station_label_by_id[station_id]


if app_status is not None and app_status.get("last_successful_refresh") is not None:
    last_refresh = format_refresh_timestamp(
        app_status["last_successful_refresh"],
    )

    st.caption(f"Ostatnia udana aktualizacja danych: {last_refresh}")


# DANE STACJI


with st.spinner("Pobieranie danych dla wybranej stacji..."):
    try:
        latest = get_latest_measurements(station_id)

    except httpx.HTTPError:
        latest = []

    try:
        forecast = get_forecast(station_id)

    except httpx.HTTPError:
        forecast = None


latest_by_param = {measurement["param"]: measurement for measurement in latest}


# GŁÓWNY WIDOK


results_col, map_col = st.columns(
    [1.05, 1],
    gap="large",
)


# POMIARY I PROGNOZA


with results_col:
    st.markdown(
        '<div class="section-title">Ostatni pomiar</div>',
        unsafe_allow_html=True,
    )

    measurement_col1, measurement_col2 = st.columns(2)

    pm10 = latest_by_param.get("PM10")
    pm25 = latest_by_param.get("PM25")

    with measurement_col1:
        if pm10 is not None and pm10["value"] is not None:
            show_measurement_card(
                param="PM10",
                value=pm10["value"],
                timestamp=pm10["timestamp"],
            )

        else:
            st.info("Brak aktualnego pomiaru PM10.")

    with measurement_col2:
        if pm25 is not None and pm25["value"] is not None:
            show_measurement_card(
                param="PM25",
                value=pm25["value"],
                timestamp=pm25["timestamp"],
            )

        else:
            st.info("Brak aktualnego pomiaru PM2.5.")

    stale_measurements = [
        measurement
        for measurement in [pm10, pm25]
        if measurement is not None and is_stale_measurement(measurement["timestamp"])
    ]

    if stale_measurements:
        st.warning("Najnowsze pomiary dla tej stacji są starsze niż 2 dni.")

    with st.expander("Szczegóły pomiarów"):
        details_col1, details_col2 = st.columns(2)

        with details_col1:
            if pm10 is not None:
                st.markdown("**PM10**")
                st.write(f"Pomiar: {format_timestamp(pm10['timestamp'])}")
                st.caption(f"Sensor: {pm10['sensor_id']}")
            else:
                st.caption("Brak danych PM10.")

        with details_col2:
            if pm25 is not None:
                st.markdown("**PM2.5**")
                st.write(f"Pomiar: {format_timestamp(pm25['timestamp'])}")
                st.caption(f"Sensor: {pm25['sensor_id']}")
            else:
                st.caption("Brak danych PM2.5.")

    st.markdown(
        '<div class="section-title">Prognoza na jutro</div>',
        unsafe_allow_html=True,
    )

    if forecast is not None:
        forecast_col1, forecast_col2 = st.columns(2)

        with forecast_col1:
            show_forecast_card(
                "PM10",
                forecast["pm10"],
                forecast["forecast_date"],
            )

        with forecast_col2:
            show_forecast_card(
                "PM25",
                forecast["pm25"],
                forecast["forecast_date"],
            )

        forecast_warnings = []

        for param_name, forecast_data in [
            ("PM10", forecast["pm10"]),
            ("PM2.5", forecast["pm25"]),
        ]:
            if forecast_data.get("warning"):
                forecast_warnings.append(f"{param_name}: {forecast_data['warning']}")

        if forecast_warnings:
            st.warning(" ".join(forecast_warnings))

        with st.expander("Kompletność danych i szczegóły prognozy"):
            st.caption(
                "Kompletność danych pokazuje, jaka część "
                "oczekiwanych pomiarów z ostatnich 7 dni "
                "była dostępna. Nie jest to poziom pewności prognozy."
            )

            pm10_forecast = forecast["pm10"]
            pm25_forecast = forecast["pm25"]

            coverage_col1, coverage_col2 = st.columns(2)

            with coverage_col1:
                st.metric(
                    "Kompletność PM10",
                    f"{pm10_forecast['coverage_7d']:.1f}%",
                )

            with coverage_col2:
                st.metric(
                    "Kompletność PM2.5",
                    f"{pm25_forecast['coverage_7d']:.1f}%",
                )

            st.divider()

            details_col1, details_col2 = st.columns(2)

            with details_col1:
                st.markdown("**PM10**")
                st.write(
                    f"Dane wejściowe do: {format_date(pm10_forecast['data_date'])}"
                )
                st.caption(f"Sensor: {pm10_forecast['sensor_id']}")

            with details_col2:
                st.markdown("**PM2.5**")
                st.write(
                    f"Dane wejściowe do: {format_date(pm25_forecast['data_date'])}"
                )
                st.caption(f"Sensor: {pm25_forecast['sensor_id']}")

            for param_name, forecast_data in [
                ("PM10", pm10_forecast),
                ("PM2.5", pm25_forecast),
            ]:
                coverage_warning = forecast_data.get("coverage_warning")

                if coverage_warning:
                    if forecast_data["coverage_status"] == "critical":
                        st.error(f"{param_name}: {coverage_warning}")
                    else:
                        st.warning(f"{param_name}: {coverage_warning}")

    else:
        st.warning(
            "Prognoza dla tej stacji jest obecnie "
            "niedostępna. Spróbuj ponownie później "
            "lub wybierz inną stację."
        )


# MAPA


with map_col:
    st.markdown(
        '<div class="section-title">Mapa stacji</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        """
<div class="map-note">
    Kliknij punkt na mapie, aby wybrać stację.
</div>
        """,
        unsafe_allow_html=True,
    )

    map_param_display = st.radio(
        "Kolor markerów",
        [
            "PM10",
            "PM2.5",
        ],
        horizontal=True,
        key="map_param",
    )

    map_param = backend_param_name(map_param_display)

    with st.spinner("Ładowanie mapy..."):
        map_data = prepare_map_data(
            stations,
            map_param,
        )

    if map_data:
        station_layer = pdk.Layer(
            "ScatterplotLayer",
            id="stations",
            data=map_data,
            get_position="[lon, lat]",
            get_fill_color="color",
            get_radius=5,
            radius_units="pixels",
            radius_min_pixels=4,
            radius_max_pixels=7,
            pickable=True,
            auto_highlight=True,
            highlight_color=[255, 255, 255, 230],
        )

        selected_station_data = next(
            (item for item in map_data if item["station_id"] == station_id),
            None,
        )

        layers = [station_layer]

        # Delikatnie wyróżnia wybraną stację.
        if selected_station_data is not None:
            selected_layer = pdk.Layer(
                "ScatterplotLayer",
                id="selected-station",
                data=[selected_station_data],
                get_position="[lon, lat]",
                get_radius=5.7,
                radius_units="pixels",
                radius_min_pixels=5.7,
                radius_max_pixels=5.7,
                stroked=True,
                filled=False,
                get_line_color=[255, 255, 255, 220],
                get_line_width=0.8,
                line_width_units="pixels",
                pickable=False,
            )

            layers.append(selected_layer)

        view_state = pdk.ViewState(
            latitude=52.0,
            longitude=19.0,
            zoom=5.8,
            min_zoom=5.0,
            max_zoom=12,
        )

        tooltip = {
            "html": (
                "<b>{name}</b><br/>"
                "{city}<br/><br/>"
                f"{map_param_display}: "
                "<b>{value} µg/m³</b><br/>"
                "Jakość: <b>{status}</b><br/>"
                "Pomiar: {age}<br/><br/>"
                "<span style='font-size:11px;'>"
                "Dane dotyczą tej stacji pomiarowej."
                "</span>"
            )
        }

        deck = pdk.Deck(
            layers=layers,
            initial_view_state=view_state,
            tooltip=tooltip,
            map_style=None,
        )

        map_event = st.pydeck_chart(
            deck,
            width="stretch",
            height=540,
            on_select="rerun",
            selection_mode="single-object",
            key=f"station_map_{station_id}",
        )

        selected_objects = (
            map_event.selection.objects.get(
                "stations",
                [],
            )
            if map_event
            else []
        )

        if selected_objects:
            clicked_station_id = int(selected_objects[0]["station_id"])

            if clicked_station_id != station_id:
                st.session_state.pending_station_id = clicked_station_id

                st.rerun()

        st.markdown(
            """
<div class="legend">
    <div class="legend-item">
        <span class="legend-dot dot-very-good"></span>
        bardzo dobry
    </div>
    <div class="legend-item">
        <span class="legend-dot dot-good"></span>
        dobry
    </div>
    <div class="legend-item">
        <span class="legend-dot dot-moderate"></span>
        umiarkowany
    </div>
    <div class="legend-item">
        <span class="legend-dot dot-sufficient"></span>
        dostateczny
    </div>
    <div class="legend-item">
        <span class="legend-dot dot-bad"></span>
        zły
    </div>
    <div class="legend-item">
        <span class="legend-dot dot-very-bad"></span>
        bardzo zły
    </div>
</div>
            """,
            unsafe_allow_html=True,
        )

    else:
        st.info("Brak danych do wyświetlenia na mapie.")


# HISTORIA


st.markdown(
    '<div class="section-title">Historia pomiarów</div>',
    unsafe_allow_html=True,
)


history_controls_col1, history_controls_col2 = st.columns([1, 1])


with history_controls_col1:
    history_param_display = st.radio(
        "Parametr",
        [
            "PM10",
            "PM2.5",
        ],
        horizontal=True,
        key="history_param",
    )


with history_controls_col2:
    history_range = st.radio(
        "Zakres",
        [
            "7 dni",
            "30 dni",
            "90 dni",
            "1 rok",
        ],
        horizontal=True,
        key="history_range",
    )


history_param = backend_param_name(history_param_display)


history_days = {
    "7 dni": 7,
    "30 dni": 30,
    "90 dni": 90,
    "1 rok": 365,
}


selected_station_data = next(
    (station for station in stations if station["id"] == station_id),
    None,
)


if selected_station_data is not None:
    station_title = selected_station_data["name"]

else:
    station_title = selected_station


aggregation_label = (
    "Średnie dobowe" if history_days[history_range] >= 90 else "Pomiary godzinowe"
)


st.markdown(
    f"""
<div class="chart-header">
    <div class="chart-title">
        {history_param_display} — {station_title}
    </div>
    <div class="chart-subtitle">
        {aggregation_label} • {history_range}
    </div>
</div>
    """,
    unsafe_allow_html=True,
)


try:
    history = get_measurements(
        station_id,
        history_param,
        history_days[history_range],
    )

except httpx.HTTPError:
    history = []

    st.error("Nie udało się pobrać historii pomiarów. Spróbuj ponownie później.")


if history:
    chart_df, completeness = prepare_history_data(
        history,
        history_days[history_range],
    )

    valid_chart_values = chart_df["value"].dropna()

    if not valid_chart_values.empty:
        average_value = valid_chart_values.mean()
        maximum_value = valid_chart_values.max()

        metric_col1, metric_col2, metric_col3 = st.columns(3)

        with metric_col1:
            st.markdown(
                f"""
<div class="summary-card">
    <div class="summary-label">Średnia</div>
    <div class="summary-value">
        {average_value:.2f} µg/m³
    </div>
</div>
                """,
                unsafe_allow_html=True,
            )

        with metric_col2:
            st.markdown(
                f"""
<div class="summary-card">
    <div class="summary-label">Maksimum</div>
    <div class="summary-value">
        {maximum_value:.2f} µg/m³
    </div>
</div>
                """,
                unsafe_allow_html=True,
            )

        with metric_col3:
            st.markdown(
                f"""
<div class="summary-card">
    <div class="summary-label">
        Kompletność danych
    </div>
    <div class="summary-value">
        {completeness:.1f}%
    </div>
</div>
                """,
                unsafe_allow_html=True,
            )

        st.markdown("<br>", unsafe_allow_html=True)

        chart_valid = chart_df.dropna(subset=["value"]).copy()

        chart_valid["local_timestamp"] = chart_valid["timestamp"].dt.tz_convert(
            "Europe/Warsaw"
        )

        if history_days[history_range] >= 90:
            chart_valid["data_tooltip"] = chart_valid["local_timestamp"].dt.strftime(
                "%d.%m.%Y"
            )

        else:
            chart_valid["data_tooltip"] = chart_valid["local_timestamp"].dt.strftime(
                "%d.%m.%Y, %H:%M"
            )

        date_from = chart_df["timestamp"].min()
        date_to = chart_df["timestamp"].max()

        axis = get_chart_axis(
            history_range,
            date_from,
            date_to,
        )

        base = alt.Chart(chart_df).encode(
            x=alt.X(
                "timestamp:T",
                axis=axis,
                scale=alt.Scale(
                    domain=[
                        date_from.to_pydatetime(),
                        date_to.to_pydatetime(),
                    ]
                ),
            ),
            y=alt.Y(
                "value:Q",
                title="Stężenie [µg/m³]",
                scale=alt.Scale(
                    zero=False,
                ),
            ),
        )

        line = base.mark_line(
            strokeWidth=2,
            tooltip=None,
        )

        nearest = alt.selection_point(
            nearest=True,
            on="pointerover",
            fields=["timestamp"],
            empty=False,
        )

        interaction_base = alt.Chart(chart_valid).encode(
            x=alt.X("timestamp:T"),
            y=alt.Y("value:Q"),
        )

        selectors = interaction_base.mark_point(
            opacity=0,
            tooltip=None,
        ).add_params(nearest)

        points = interaction_base.mark_point(
            size=90,
            tooltip=None,
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
                    title=f"{history_param_display} [µg/m³]",
                    format=".2f",
                ),
            ],
        )

        rules = (
            alt.Chart(chart_valid)
            .mark_rule(
                tooltip=None,
            )
            .encode(
                x="timestamp:T",
                opacity=alt.condition(
                    nearest,
                    alt.value(0.22),
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
        ).properties(
            height=390,
        )

        st.altair_chart(
            chart,
            width="stretch",
        )

        st.caption("Przerwy na wykresie oznaczają brak dostępnych pomiarów.")

    else:
        st.info("Brak prawidłowych pomiarów w wybranym okresie.")

else:
    st.info("Brak historii pomiarów dla wybranego okresu.")


# ŹRÓDŁA


st.markdown(
    """
<div class="source-footer">
    Dane o jakości powietrza:
    <b>Główny Inspektorat Ochrony Środowiska (GIOŚ)</b>
    &nbsp;&nbsp;•&nbsp;&nbsp;
    Dane meteorologiczne:
    <b>Open-Meteo</b>
</div>
    """,
    unsafe_allow_html=True,
)
