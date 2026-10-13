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

APP_ENV = os.getenv("APP_ENV", "local")
IS_PRODUCTION = APP_ENV == "production"

LOGO_PATH = Path(__file__).parent / "assets" / "logo.png"


# Przygotowuje logo do wyświetlenia.
def get_logo_base64():
    with open(LOGO_PATH, "rb") as logo_file:
        return base64.b64encode(logo_file.read()).decode()


logo_base64 = get_logo_base64()

QUALITY_COLORS = {
    "quality-very-good": [0, 180, 0],
    "quality-good": [100, 200, 0],
    "quality-moderate": [255, 200, 0],
    "quality-sufficient": [255, 140, 0],
    "quality-bad": [220, 0, 0],
    "quality-very-bad": [140, 0, 0],
}

AIR_QUALITY_LEVELS = {
    "PM10": [
        (20.0, "Bardzo dobry", "card-very-good", "quality-very-good"),
        (50.0, "Dobry", "card-good", "quality-good"),
        (80.0, "Umiarkowany", "card-moderate", "quality-moderate"),
        (110.0, "Dostateczny", "card-sufficient", "quality-sufficient"),
        (150.0, "Zły", "card-bad", "quality-bad"),
    ],
    "PM25": [
        (13.0, "Bardzo dobry", "card-very-good", "quality-very-good"),
        (35.0, "Dobry", "card-good", "quality-good"),
        (55.0, "Umiarkowany", "card-moderate", "quality-moderate"),
        (75.0, "Dostateczny", "card-sufficient", "quality-sufficient"),
        (110.0, "Zły", "card-bad", "quality-bad"),
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


/* GŁÓWNY UKŁAD */

.block-container {
    padding-top: 48px;
    padding-bottom: 2rem;
    padding-left: 2rem;
    padding-right: 2rem;
    max-width: 1700px;
}


/* NAGŁÓWKI SEKCJI */

.section-title {
    font-size: 24px;
    font-weight: 700;
    margin-top: 14px;
    margin-bottom: 8px;
}

.section-subtitle {
    font-size: 14px;
    opacity: 0.65;
    margin-top: -2px;
    margin-bottom: 10px;
}


/* KARTY */

.measurement-card,
.forecast-card {
    padding: 16px 18px;
    border-radius: 12px;
    border: 1px solid rgba(128, 128, 128, 0.22);
    box-sizing: border-box;
    min-height: 150px;
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
    font-size: 12px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    opacity: 0.65;
    margin-bottom: 4px;
}

.card-param {
    font-size: 16px;
    font-weight: 650;
}

.card-value {
    font-size: 31px;
    font-weight: 750;
    margin-top: 5px;
    margin-bottom: 3px;
}

.card-status {
    font-size: 15px;
    font-weight: 650;
    margin-bottom: 6px;
}


/* KOLORY JAKOŚCI */

.quality-very-good {
    color: rgb(0, 180, 0);
}

.quality-good {
    color: rgb(100, 200, 0);
}

.quality-moderate {
    color: rgb(255, 200, 0);
}

.quality-sufficient {
    color: rgb(255, 140, 0);
}

.quality-bad {
    color: rgb(220, 0, 0);
}

.quality-very-bad {
    color: rgb(140, 0, 0);
}

.card-info {
    font-size: 13px;
    line-height: 1.4;
    opacity: 0.72;
}

.cards-bottom-gap {
    height: 20px;
}


/* MAPA */

.map-note {
    font-size: 13px;
    opacity: 0.68;
    margin-top: -2px;
    margin-bottom: 5px;
}

.legend {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    margin-top: 5px;
    margin-bottom: 5px;
    font-size: 12px;
}

.legend-item {
    display: flex;
    align-items: center;
    gap: 5px;
}

.legend-dot {
    width: 10px;
    height: 10px;
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


/* TOP BAR */

.top-bar {
    position: fixed;
    top: 0;
    left: 0;
    width: 100vw;
    height: 60px;
    z-index: 999;

    display: flex;
    align-items: center;
    justify-content: space-between;

    padding: 0 120px 0 32px;
    box-sizing: border-box;

    background-color: #ffffff !important;
    background-image: none !important;

    color: #262730 !important;
    opacity: 1 !important;

    border-bottom: 1px solid rgba(128, 128, 128, 0.25);

    box-shadow:
        0 2px 12px rgba(0, 0, 0, 0.20);
}

.top-bar-logo {
    display: flex;
    align-items: center;
    gap: 8px;

    font-size: 22px;
    font-weight: 700;

    color: inherit !important;
}

.top-bar-logo span {
    color: inherit !important;
}

.top-bar-logo-img {
    width: 32px;
    height: 32px;
    object-fit: contain;
}

.top-bar-subtitle {
    font-size: 13px;
    color: inherit !important;
    opacity: 0.68;
    font-weight: 400;
    white-space: nowrap;
}


/* WYBÓR STACJI - DESKTOP */

.st-key-station_controls_mobile {
    display: none;
}

.station-inline-label {
    font-size: 18px;
    font-weight: 650;
    line-height: 38px;
    white-space: nowrap;
}

.station-refresh {
    font-size: 13px;
    line-height: 38px;
    opacity: 0.68;
    white-space: nowrap;
}

.st-key-station_controls_desktop
div[data-testid="stHorizontalBlock"] {
    align-items: center;
    gap: 12px;
}

.st-key-station_controls_desktop
div[data-testid="stHorizontalBlock"]
> div[data-testid="stColumn"]:nth-child(1) {
    flex: 0 0 auto !important;
    width: auto !important;
    min-width: 120px !important;
}

.st-key-station_controls_desktop
div[data-testid="stHorizontalBlock"]
> div[data-testid="stColumn"]:nth-child(2) {
    flex: 0 0 300px !important;
    width: 300px !important;
    max-width: 300px !important;
}

.st-key-station_controls_desktop
div[data-testid="stHorizontalBlock"]
> div[data-testid="stColumn"]:nth-child(3) {
    flex: 1 1 auto !important;
    width: auto !important;
}

.st-key-station_controls_desktop
div[data-testid="stSelectbox"] {
    width: 300px !important;
    max-width: 300px !important;
}


/* EXPANDERY */

div[data-testid="stExpander"] {
    border: 1px solid rgba(128, 128, 128, 0.22);
    border-radius: 10px;
    overflow: hidden;
}

div[data-testid="stExpander"] details summary {
    padding-top: 4px;
    padding-bottom: 4px;
}


/* HISTORIA */

.chart-header {
    margin-top: 6px;
    margin-bottom: 14px;
}

.chart-title {
    font-size: 24px;
    font-weight: 700;
    margin-bottom: 4px;
}

.chart-subtitle {
    font-size: 14px;
    opacity: 0.65;
}

.summary-card {
    padding: 12px 15px;
    border-radius: 10px;
    background: rgba(128, 128, 128, 0.07);
    border: 1px solid rgba(128, 128, 128, 0.16);
    min-height: 78px;
}

.summary-label {
    font-size: 12px;
    opacity: 0.65;
    margin-bottom: 5px;
}

.summary-value {
    font-size: 23px;
    font-weight: 700;
}


/* STOPKA */

.source-footer {
    margin-top: 28px;
    padding-top: 14px;
    padding-bottom: 10px;

    border-top: 1px solid rgba(128, 128, 128, 0.2);

    text-align: center;

    font-size: 13px;
    line-height: 1.5;

    opacity: 0.78;
}


/* MOBILE */

@media (max-width: 768px) {

    div[data-testid="stMainBlockContainer"] {
        padding-top: 48px !important;
        padding-left: 1rem !important;
        padding-right: 1rem !important;
        padding-bottom: 2rem !important;
        max-width: 100% !important;
    }

    .top-bar {
        width: 100vw;
        height: 64px;
        padding: 0 16px;
        justify-content: flex-start;

        box-shadow:
            0 2px 12px rgba(0, 0, 0, 0.10);
    }

    .top-bar-logo {
        gap: 8px;
        font-size: 21px;
    }

    .top-bar-logo-img {
        width: 32px;
        height: 32px;
    }

    .top-bar-subtitle {
        display: none !important;
    }

    .section-title {
        font-size: 20px;
        margin-top: 10px;
        margin-bottom: 7px;
    }

    .measurement-card,
    .forecast-card {
        min-height: auto;
        padding: 15px;
    }

    .card-label {
        font-size: 11px;
    }

    .card-param {
        font-size: 14px;
    }

    .card-value {
        font-size: 25px;
        margin-top: 4px;
    }

    .card-status {
        font-size: 13px;
        margin-bottom: 5px;
    }

    .card-info {
        font-size: 12px;
    }

    .legend {
        gap: 9px;
        font-size: 11px;
    }

    .summary-value {
        font-size: 20px;
    }


    /* DESKTOPOWY WYBÓR STACJI ZNIKA */

    .st-key-station_controls_desktop {
        display: none !important;
    }


    /* MOBILNY WYBÓR STACJI */

    .st-key-station_controls_mobile {
        display: block !important;
        width: 100% !important;
        margin: -6px 0 4px 0 !important;
        padding: 0 !important;
    }

    .st-key-station_controls_mobile
    div[data-testid="stSelectbox"] {
        width: 100% !important;
        max-width: 100% !important;
        margin-top: 0 !important;
    }

    .st-key-station_controls_mobile
    div[data-testid="stSelectbox"] > label {
        margin-bottom: 5px !important;
    }

    .st-key-station_controls_mobile
    div[data-testid="stSelectbox"] > label p {
        font-size: 16px !important;
        font-weight: 650 !important;
        line-height: 1.25 !important;
    }

    .mobile-refresh {
        font-size: 12px;
        line-height: 1.35;
        opacity: 0.68;
        margin-top: 5px;
        margin-bottom: 4px;
    }

    .source-footer {
        font-size: 12px;
    }
}


/* KARTY W JEDNEJ KOLUMNIE */

@media (max-width: 640px) {

    .measurement-card,
    .forecast-card,
    .summary-card {
        margin-bottom: 14px !important;
    }
}


/* TELEFONY */

@media (max-width: 560px) {

    div[data-testid="stMainBlockContainer"] {
        padding-top: 46px !important;
        padding-left: 14px !important;
        padding-right: 14px !important;
    }

    .top-bar {
        padding: 0 14px;
    }

    .top-bar-logo {
        font-size: 20px;
    }

    .top-bar-logo-img {
        width: 31px;
        height: 31px;
    }

    .section-title {
        font-size: 18px;
        margin-top: 9px;
        margin-bottom: 6px;
    }

    .section-subtitle {
        font-size: 12px;
    }

    .measurement-card,
    .forecast-card {
        padding: 13px;
    }

    .card-label {
        font-size: 10px;
        margin-bottom: 3px;
    }

    .card-param {
        font-size: 13px;
    }

    .card-value {
        font-size: 22px;
        margin-top: 3px;
        margin-bottom: 3px;
    }

    .card-status {
        font-size: 12px;
        margin-bottom: 4px;
    }

    .card-info {
        font-size: 11px;
        line-height: 1.35;
    }

    .chart-title {
        font-size: 18px;
    }

    .chart-subtitle {
        font-size: 12px;
    }

    .summary-card {
        padding: 10px 12px;
        min-height: 72px;
    }

    .summary-value {
        font-size: 18px;
    }

    .summary-label {
        font-size: 10px;
    }

    .map-note {
        font-size: 11px;
    }

    .legend {
        gap: 7px;
        font-size: 10px;
    }

    .cards-bottom-gap {
        height: 12px;
    }

    .st-key-station_controls_mobile {
        margin-top: -8px !important;
    }

    .st-key-station_controls_mobile
    div[data-testid="stSelectbox"] > label p {
        font-size: 15px !important;
    }

    .mobile-refresh {
        font-size: 11px;
    }

    .source-footer {
        font-size: 11px;
    }
}


/* MAŁE TELEFONY */

@media (max-width: 360px) {

    div[data-testid="stMainBlockContainer"] {
        padding-top: 44px !important;
        padding-left: 12px !important;
        padding-right: 12px !important;
    }

    .top-bar {
        padding: 0 12px;
    }

    .top-bar-logo {
        font-size: 19px;
    }

    .top-bar-logo-img {
        width: 30px;
        height: 30px;
    }

    .section-title {
        font-size: 17px;
    }

    .measurement-card,
    .forecast-card {
        padding: 12px;
    }

    .card-label {
        font-size: 10px;
    }

    .card-param {
        font-size: 12px;
    }

    .card-value {
        font-size: 21px;
    }

    .card-status {
        font-size: 11px;
    }

    .card-info {
        font-size: 10px;
    }

    .chart-title {
        font-size: 17px;
    }

    .chart-subtitle {
        font-size: 11px;
    }

    .summary-card {
        padding: 10px 11px;
    }

    .summary-value {
        font-size: 17px;
    }

    .summary-label {
        font-size: 10px;
    }

    .map-note {
        font-size: 10px;
    }

    .legend {
        font-size: 9px;
        gap: 6px;
    }

    .st-key-station_controls_mobile {
        margin-top: -10px !important;
    }

    .st-key-station_controls_mobile
    div[data-testid="stSelectbox"] > label p {
        font-size: 14px !important;
    }

    .mobile-refresh {
        font-size: 10px;
    }
}

</style>
    """,
    unsafe_allow_html=True,
)


# FORMATOWANIE


def format_timestamp(timestamp_text):
    timestamp = pd.to_datetime(
        timestamp_text,
        utc=True,
    )

    timestamp = timestamp.tz_convert("Europe/Warsaw")

    return timestamp.strftime("%d.%m.%Y, %H:%M")


def format_refresh_timestamp(timestamp_text):
    timestamp = pd.to_datetime(
        timestamp_text,
        utc=True,
    )

    timestamp = timestamp.tz_convert("Europe/Warsaw")

    return timestamp.strftime("%d.%m.%Y, %H:%M")


def format_date(date_text):
    formatted_date = pd.to_datetime(date_text)

    return formatted_date.strftime("%d.%m.%Y")


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


def is_stale_measurement(timestamp_text):
    timestamp = pd.to_datetime(
        timestamp_text,
        utc=True,
    )

    age = pd.Timestamp.now(tz="UTC") - timestamp

    return age > pd.Timedelta(days=2)


def display_param_name(param):
    if param == "PM25":
        return "PM2.5"

    return param


def backend_param_name(param):
    if param == "PM2.5":
        return "PM25"

    return param


# API


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


@st.cache_data(ttl=60)
def get_stations():
    response = get_with_retry(
        f"{API_URL}/stations",
        timeout=30.0,
    )

    return response.json()


@st.cache_data(ttl=60)
def get_app_status():
    response = get_with_retry(
        f"{API_URL}/status",
        timeout=30.0,
    )

    return response.json()


@st.cache_data(ttl=60)
def get_latest_measurements(station_id):
    response = get_with_retry(
        f"{API_URL}/stations/{station_id}/latest",
        timeout=30.0,
    )

    return response.json()


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


@st.cache_data(ttl=300)
def get_forecast(station_id):
    response = get_with_retry(
        f"{API_URL}/stations/{station_id}/forecast",
        timeout=60.0,
    )

    return response.json()


# STATUS I KOLORY


def get_status(value, param):
    for (
        threshold,
        name,
        card_class,
        quality_class,
    ) in AIR_QUALITY_LEVELS[param]:
        if value <= threshold:
            return {
                "name": name,
                "class": card_class,
                "quality_class": quality_class,
                "color": QUALITY_COLORS[quality_class],
            }

    return {
        "name": "Bardzo zły",
        "class": "card-very-bad",
        "quality_class": "quality-very-bad",
        "color": QUALITY_COLORS["quality-very-bad"],
    }


# KARTY


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
    <div class="card-status {status["quality_class"]}">
        {status["name"]}
    </div>
    <div class="card-info">
        {format_timestamp(timestamp)}<br>
        {get_measurement_age(timestamp)}
    </div>
</div>
        """,
        unsafe_allow_html=True,
    )


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
    <div class="card-status {status["quality_class"]}">
        {status["name"]}
    </div>
    <div class="card-info">
        Prognozowana średnia dobowa<br>
        {format_date(forecast_date)}
    </div>
</div>
        """,
        unsafe_allow_html=True,
    )


# MAPA


def get_latest_pollutant(
    station_id,
    param,
):
    measurements = get_latest_measurements(station_id)

    for measurement in measurements:
        if measurement["param"] == param:
            return measurement

    return None


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
                "quality_class": status["quality_class"],
                "color": status["color"],
            }
        )

    return map_data


# WYKRES


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


# Dopasowuje top bar do motywu przeglądarki.
st.html(
    """
<script>
(() => {
    const updateTopBar = () => {
        const app = document.querySelector(".stApp");
        const bar = document.querySelector(".top-bar");

        if (!app || !bar) {
            return;
        }

        const appStyle = window.getComputedStyle(app);
        const background = appStyle.backgroundColor;
        const textColor = appStyle.color;

        if (
            background &&
            background !== "transparent" &&
            background !== "rgba(0, 0, 0, 0)"
        ) {
            bar.style.setProperty(
                "background-color",
                background,
                "important"
            );
        }

        if (textColor) {
            bar.style.setProperty(
                "color",
                textColor,
                "important"
            );
        }

        bar.style.setProperty(
            "background-image",
            "none",
            "important"
        );

        bar.style.setProperty(
            "opacity",
            "1",
            "important"
        );
    };

    if (window.smogcastTopBarInterval) {
        clearInterval(window.smogcastTopBarInterval);
    }

    updateTopBar();

    window.smogcastTopBarInterval = setInterval(
        updateTopBar,
        500
    );
})();
</script>
    """,
    unsafe_allow_javascript=True,
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


if "last_map_selection_id" not in st.session_state:
    st.session_state.last_map_selection_id = None


# Obsługuje wybór z mapy.
if "pending_station_id" in st.session_state:
    pending_station_id = st.session_state.pop("pending_station_id")

    if pending_station_id in station_label_by_id:
        st.session_state.selected_station_id = pending_station_id


if "selected_station_id" not in st.session_state:
    st.session_state.selected_station_id = stations[0]["id"]


if st.session_state.selected_station_id not in station_label_by_id:
    st.session_state.selected_station_id = stations[0]["id"]


# Synchronizuje desktop i mobile.
selected_station_label = station_label_by_id[st.session_state.selected_station_id]


if st.session_state.get("station_selector_desktop") != selected_station_label:
    st.session_state["station_selector_desktop"] = selected_station_label


if st.session_state.get("station_selector_mobile") != selected_station_label:
    st.session_state["station_selector_mobile"] = selected_station_label


# Wybór stacji na desktopie.
def update_station_from_desktop():
    selected_label = st.session_state["station_selector_desktop"]

    st.session_state.selected_station_id = station_options[selected_label]


# Wybór stacji na telefonie.
def update_station_from_mobile():
    selected_label = st.session_state["station_selector_mobile"]

    st.session_state.selected_station_id = station_options[selected_label]


last_refresh = None


if app_status is not None and app_status.get("last_successful_refresh") is not None:
    last_refresh = format_refresh_timestamp(
        app_status["last_successful_refresh"],
    )


# DESKTOP


with st.container(key="station_controls_desktop"):
    (
        station_label_col,
        station_select_col,
        station_refresh_col,
    ) = st.columns(
        [1, 2, 5],
        gap="small",
    )

    with station_label_col:
        st.markdown(
            '<div class="station-inline-label">Wybierz stację:</div>',
            unsafe_allow_html=True,
        )

    with station_select_col:
        st.selectbox(
            "Stacja pomiarowa",
            station_labels,
            key="station_selector_desktop",
            on_change=update_station_from_desktop,
            label_visibility="collapsed",
        )

    with station_refresh_col:
        if last_refresh is not None:
            st.markdown(
                (
                    '<div class="station-refresh">'
                    "Ostatnia udana aktualizacja danych: "
                    f"{last_refresh}"
                    "</div>"
                ),
                unsafe_allow_html=True,
            )


# MOBILE


with st.container(key="station_controls_mobile"):
    st.selectbox(
        "Wybierz stację:",
        station_labels,
        key="station_selector_mobile",
        on_change=update_station_from_mobile,
        label_visibility="visible",
        width="stretch",
    )

    if last_refresh is not None:
        st.markdown(
            (
                '<div class="mobile-refresh">'
                "Ostatnia udana aktualizacja danych: "
                f"{last_refresh}"
                "</div>"
            ),
            unsafe_allow_html=True,
        )


station_id = st.session_state.selected_station_id

selected_station = station_label_by_id[station_id]


# ZAKŁADKI


current_tab, history_tab = st.tabs(
    [
        "Aktualne dane",
        "Historia pomiarów",
    ],
    key="main_tabs",
    on_change="rerun",
)


# AKTUALNE DANE


with current_tab:
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

        st.markdown(
            '<div class="cards-bottom-gap"></div>',
            unsafe_allow_html=True,
        )

        stale_measurements = [
            measurement
            for measurement in [pm10, pm25]
            if (
                measurement is not None
                and is_stale_measurement(measurement["timestamp"])
            )
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

            st.markdown(
                '<div class="cards-bottom-gap"></div>',
                unsafe_allow_html=True,
            )

            forecast_warnings = []

            for param_name, forecast_data in [
                ("PM10", forecast["pm10"]),
                ("PM2.5", forecast["pm25"]),
            ]:
                if forecast_data.get("warning"):
                    forecast_warnings.append(
                        f"{param_name}: {forecast_data['warning']}"
                    )

            if forecast_warnings:
                st.warning(" ".join(forecast_warnings))

            with st.expander("Kompletność danych i szczegóły prognozy"):
                st.caption(
                    "Kompletność danych pokazuje, "
                    "jaka część oczekiwanych pomiarów "
                    "z ostatnich 7 dni była dostępna. "
                    "Nie jest to poziom pewności prognozy."
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
            '<div class="map-note">Kliknij punkt na mapie, aby wybrać stację.</div>',
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
                highlight_color=[
                    255,
                    255,
                    255,
                    230,
                ],
            )

            selected_station_data = next(
                (item for item in map_data if item["station_id"] == station_id),
                None,
            )

            layers = [station_layer]

            # Wyróżnia wybraną stację.
            if selected_station_data is not None:
                selected_quality_class = selected_station_data["quality_class"]

                selected_color = QUALITY_COLORS[selected_quality_class]

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
                    get_line_color=[
                        *selected_color,
                        153,
                    ],
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
                    "Jakość: "
                    "<b>{status}</b><br/>"
                    "Pomiar: {age}<br/><br/>"
                    "<span style='font-size:11px;'>"
                    "Dane dotyczą tej stacji "
                    "pomiarowej."
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
                height=470,
                on_select="rerun",
                selection_mode="single-object",
                key="station_map",
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

                # Reaguje tylko na nowe kliknięcie.
                if clicked_station_id != st.session_state.last_map_selection_id:
                    st.session_state["last_map_selection_id"] = clicked_station_id

                    if clicked_station_id != station_id:
                        st.session_state["pending_station_id"] = clicked_station_id

                        st.rerun()

            else:
                st.session_state["last_map_selection_id"] = None

            st.markdown(
                """
<div class="legend">
<div class="legend-item">
    <span class="legend-dot dot-very-good"></span>bardzo dobry
</div>
<div class="legend-item">
    <span class="legend-dot dot-good"></span>dobry
</div>
<div class="legend-item">
    <span class="legend-dot dot-moderate"></span>umiarkowany
</div>
<div class="legend-item">
    <span class="legend-dot dot-sufficient"></span>dostateczny
</div>
<div class="legend-item">
    <span class="legend-dot dot-bad"></span>zły
</div>
<div class="legend-item">
    <span class="legend-dot dot-very-bad"></span>bardzo zły
</div>
</div>
                """,
                unsafe_allow_html=True,
            )

        else:
            st.info("Brak danych do wyświetlenia na mapie.")


# HISTORIA POMIARÓW


if history_tab.open:
    with history_tab:
        st.markdown(
            '<div class="section-title">Historia pomiarów</div>',
            unsafe_allow_html=True,
        )

        (
            history_controls_col1,
            history_controls_col2,
        ) = st.columns([1, 1])

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
            "Średnie dobowe"
            if history_days[history_range] >= 90
            else "Pomiary godzinowe"
        )

        st.markdown(
            (
                '<div class="chart-header">'
                '<div class="chart-title">'
                f"{history_param_display} — "
                f"{station_title}"
                "</div>"
                '<div class="chart-subtitle">'
                f"{aggregation_label} • "
                f"{history_range}"
                "</div>"
                "</div>"
            ),
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

            st.error(
                "Nie udało się pobrać historii pomiarów. Spróbuj ponownie później."
            )

        if history:
            chart_df, completeness = prepare_history_data(
                history,
                history_days[history_range],
            )

            valid_chart_values = chart_df["value"].dropna()

            if not valid_chart_values.empty:
                average_value = valid_chart_values.mean()
                maximum_value = valid_chart_values.max()

                (
                    metric_col1,
                    metric_col2,
                    metric_col3,
                ) = st.columns(3)

                with metric_col1:
                    st.markdown(
                        (
                            '<div class="summary-card">'
                            '<div class="summary-label">'
                            "Średnia"
                            "</div>"
                            '<div class="summary-value">'
                            f"{average_value:.2f} µg/m³"
                            "</div>"
                            "</div>"
                        ),
                        unsafe_allow_html=True,
                    )

                with metric_col2:
                    st.markdown(
                        (
                            '<div class="summary-card">'
                            '<div class="summary-label">'
                            "Maksimum"
                            "</div>"
                            '<div class="summary-value">'
                            f"{maximum_value:.2f} µg/m³"
                            "</div>"
                            "</div>"
                        ),
                        unsafe_allow_html=True,
                    )

                with metric_col3:
                    st.markdown(
                        (
                            '<div class="summary-card">'
                            '<div class="summary-label">'
                            "Kompletność danych"
                            "</div>"
                            '<div class="summary-value">'
                            f"{completeness:.1f}%"
                            "</div>"
                            "</div>"
                        ),
                        unsafe_allow_html=True,
                    )

                st.markdown(
                    "<br>",
                    unsafe_allow_html=True,
                )

                chart_valid = chart_df.dropna(subset=["value"]).copy()

                chart_valid["local_timestamp"] = chart_valid["timestamp"].dt.tz_convert(
                    "Europe/Warsaw"
                )

                if history_days[history_range] >= 90:
                    chart_valid["data_tooltip"] = chart_valid[
                        "local_timestamp"
                    ].dt.strftime("%d.%m.%Y")

                else:
                    chart_valid["data_tooltip"] = chart_valid[
                        "local_timestamp"
                    ].dt.strftime("%d.%m.%Y, %H:%M")

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
                            title=(f"{history_param_display} [µg/m³]"),
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
                    height=360,
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
