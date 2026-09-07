## 2. Schemat danych

System wykorzystuje następujące tabele:


### stations

Przechowuje informacje o stacjach pomiarowych.

| Kolumna | Typ / rola | Opis |
|---|---|---|
| `id` | PK | unikalny identyfikator stacji |
| `name` |  | nazwa stacji |
| `city` |  | miasto |
| `latitude` |  | szerokość geograficzna |
| `longitude` |  | długość geograficzna |


### sensors

Przechowuje informacje o sensorach przypisanych do stacji.

| Kolumna | Typ / rola | Opis |
|---|---|---|
| `id` | PK | unikalny identyfikator sensora |
| `station_id` | FK | identyfikator stacji |
| `param_code` |  | kod mierzonego parametru, np. `PM10`, `PM2.5` |

Relacja:

`stations.id -> sensors.station_id`

Jedna stacja może posiadać wiele sensorów, również więcej niż jeden sensor mierzący ten sam parametr.

Podczas wykonywania bieżącej prognozy system sprawdza dostępne sensory dla danego parametru i wybiera sensor posiadający najświeższe dostępne dane.


### measurements

Przechowuje surowe pomiary jakości powietrza.

| Kolumna | Typ / rola | Opis |
|---|---|---|
| `id` | PK | unikalny identyfikator pomiaru |
| `sensor_id` | FK | identyfikator sensora |
| `timestamp` | UTC | czas wykonania pomiaru |
| `value` | nullable | wartość stężenia w µg/m³ |

Relacja:

`sensors.id -> measurements.sensor_id`

Dodatkowe ograniczenie:

`UNIQUE(sensor_id, timestamp)`

Oznacza to, że dla jednego sensora nie może istnieć więcej niż jeden pomiar dla tego samego momentu czasu.

Kolumna `value` jest nullable. Brak wartości oznacza brak pomiaru i nie może być automatycznie zastępowany wartością `0`.

Dane pomiarowe są uzupełniane z dwóch źródeł API GIOŚ:

- endpointu archiwalnego – wykorzystywanego do uzupełniania starszych braków,
- endpointu bieżącego – wykorzystywanego do pobierania najnowszych dostępnych pomiarów.

Jeżeli bieżący endpoint GIOŚ nie udostępnia danych dla konkretnego sensora, system wykorzystuje najświeższe dane dostępne w bazie.


### weather

Przechowuje historyczne dane pogodowe dla lokalizacji stacji.

| Kolumna | Typ / rola | Opis |
|---|---|---|
| `id` | PK | unikalny identyfikator rekordu pogodowego |
| `station_id` | FK | identyfikator stacji |
| `timestamp` |  | czas pomiaru pogodowego |
| `temp_c` |  | temperatura w °C |
| `wind_ms` |  | prędkość wiatru w m/s |
| `humidity` |  | wilgotność |
| `pressure_hpa` |  | ciśnienie w hPa |
| `precip_mm` |  | opad w mm |

Relacja:

`stations.id -> weather.station_id`

Historyczne dane pogodowe są przypisywane do lokalizacji stacji i wykorzystywane podczas przygotowywania danych treningowych.

Podczas wykonywania prognozy na kolejny dzień system pobiera prognozę pogody bezpośrednio z Open-Meteo.

Do modelu trafiają:

- temperatura,
- prędkość wiatru,
- wilgotność.

Prognoza pogody jest wykorzystywana jako wejście modelu, ale nie jest zwracana użytkownikowi w odpowiedzi endpointu prognozy.


### daily_measurements

Przechowuje dobowe agregaty pomiarów jakości powietrza.

| Kolumna | Opis |
|---|---|
| `station_id` | identyfikator stacji |
| `param_code` | parametr, np. `PM10` lub `PM2.5` |
| `date` | dzień |
| `mean_value` | średnia dobowa |
| `max_value` | maksymalna wartość dobowa |
| `coverage` | stopień pokrycia danych w danym dniu |

Tabela powstaje na etapie przetwarzania danych i jest wykorzystywana do budowy cech oraz wykonywania predykcji.

Podczas wykonywania bieżącej prognozy agregaty dobowe są aktualizowane na podstawie sensorów wybranych jako najaktualniejsze dla PM10 i PM2.5.

Pozwala to uniknąć mieszania danych pochodzących z kilku różnych sensorów tego samego parametru.


### predictions

Przechowuje prognozy wygenerowane przez model.

| Kolumna | Typ / rola | Opis |
|---|---|---|
| `id` | PK | unikalny identyfikator prognozy |
| `station_id` | FK | identyfikator stacji |
| `param_code` |  | prognozowany parametr |
| `target_date` |  | dzień, którego dotyczy prognoza |
| `predicted_value` |  | przewidywane stężenie |
| `model_version` |  | wersja modelu |
| `created_at` |  | czas utworzenia prognozy |

Relacja:

`stations.id -> predictions.station_id`

PM10 i PM2.5 są prognozowane niezależnie i mogą być zapisywane jako osobne rekordy.

Połączenie wyników następuje dopiero na poziomie odpowiedzi API.


### Relacje między tabelami

```text
stations
   │
   ├──< sensors
   │      │
   │      └──< measurements
   │
   ├──< weather
   │
   ├──< daily_measurements
   │
   └──< predictions
```


## 3. Kontrakt API

API zostało zaprojektowane od strony potrzeb dashboardu.

Dashboard powinien umożliwiać:

- wybór stacji,
- podgląd ostatnich pomiarów,
- uzyskanie prognozy jakości powietrza na kolejny dzień.

Prognoza dla wybranej stacji zawiera jednocześnie wartości PM10 i PM2.5.

Oba parametry są jednak pobierane, przetwarzane i prognozowane niezależnie.


### GET /stations

Zwraca listę stacji dostępnych w aplikacji.

Metoda:

`GET`

Parametry:

Brak.

Przykładowe zapytanie:

`GET /stations`

Przykładowa odpowiedź:

```json
[
  {
    "id": 814,
    "name": "Katowice, ul. Kossutha",
    "city": "Katowice",
    "latitude": 50.2649,
    "longitude": 19.0238
  },
  {
    "id": 400,
    "name": "Kraków",
    "city": "Kraków",
    "latitude": 50.0647,
    "longitude": 19.945
  }
]
```


### GET /stations/{station_id}/measurements

Zwraca pomiary jakości powietrza dla wybranej stacji.

Metoda:

`GET`

Parametry ścieżki:

- `station_id` – identyfikator stacji.

Parametry zapytania mogą określać m.in.:

- parametr PM,
- początek zakresu czasu,
- koniec zakresu czasu.

Przykładowe zapytanie:

`GET /stations/117/measurements?param=PM10`

Endpoint umożliwia pobieranie danych pomiarowych używanych m.in. do prezentacji historii jakości powietrza w dashboardzie.


### GET /stations/{station_id}/latest

Zwraca najnowsze dostępne pomiary dla wybranej stacji.

Metoda:

`GET`

Parametry ścieżki:

- `station_id` – identyfikator stacji.

Przykładowe zapytanie:

`GET /stations/117/latest`


### GET /stations/{station_id}/forecast

Zwraca prognozę jakości powietrza na kolejny dzień dla wybranej stacji.

Metoda:

`GET`

Parametry ścieżki:

- `station_id` – identyfikator stacji.

Parametry zapytania:

Brak.

Przykładowe zapytanie:

`GET /stations/117/forecast`

Przykładowa odpowiedź:

```json
{
  "station_id": 117,
  "forecast_date": "2026-09-08",
  "pm10": {
    "forecast_value": 41.2,
    "threshold": 50.0,
    "alarm": false,
    "data_date": "2026-07-30",
    "data_age_days": 39,
    "data_status": "stale",
    "warning": "Forecast is based on older PM data. Latest available measurement is from 2026-07-30."
  },
  "pm25": {
    "forecast_value": 18.7,
    "threshold": 25.0,
    "alarm": false,
    "data_date": "2026-09-07",
    "data_age_days": 0,
    "data_status": "fresh",
    "warning": null
  }
}
```

PM10 i PM2.5 są prognozowane niezależnie.

Dla każdego parametru system:

1. wyszukuje sensory przypisane do wybranej stacji,
2. sprawdza dostępność najnowszych danych,
3. wybiera sensor posiadający najświeższe dostępne pomiary,
4. próbuje uzupełnić brakujące dane z API GIOŚ,
5. aktualizuje dobowe agregaty,
6. pobiera prognozę pogody na kolejny dzień,
7. buduje cechy wejściowe modelu,
8. wykonuje predykcję,
9. sprawdza próg alarmowy,
10. określa aktualność danych wejściowych.

Dla każdego parametru odpowiedź zawiera:

- `forecast_value` – prognozowane stężenie,
- `threshold` – próg wykorzystywany przez system do ustawienia flagi alarmu,
- `alarm` – informację o przekroczeniu progu,
- `data_date` – datę najnowszych danych wejściowych PM,
- `data_age_days` – wiek danych w dniach,
- `data_status` – status aktualności danych,
- `warning` – ostrzeżenie w przypadku wykorzystania starszych danych.

Dane mają status:

`fresh`

jeżeli ich wiek wynosi maksymalnie 2 dni.

Jeżeli najnowsze dostępne dane są starsze niż 2 dni, prognoza nadal może zostać wykonana, ale otrzymuje status:

`stale`

oraz odpowiednie ostrzeżenie w polu `warning`.

Dzięki temu system wykorzystuje najświeższe możliwe dane, ale jednocześnie informuje użytkownika o ich aktualności.


## 4. Przepływ danych

System wykorzystuje dwa główne przepływy danych:

1. przepływ historyczny – służący do przygotowania danych i trenowania modelu,
2. przepływ bieżący – służący do wykonywania prognozy dla użytkownika.


### 4.1. Przepływ danych historycznych

```text
GIOŚ – dane archiwalne PM
            │
            ▼
       pliki Parquet
            │
            ▼
       measurements
            │
            ▼
    daily_measurements
            │
            ▼
     cechy historyczne
     ├── PM lag 1d
     ├── PM mean 3d
     ├── PM mean 7d
     ├── miesiąc
     ├── dzień tygodnia
     ├── weekend
     └── sezon grzewczy
            │
            │
            ├───────────────┐
            │               │
            ▼               ▼
          PM         Open-Meteo archive
                             │
                             ▼
                       dane pogodowe
                       ├── temperatura
                       ├── wiatr
                       └── wilgotność
            │               │
            └───────┬───────┘
                    ▼
                 features
                    │
                    ▼
                model ML
                    │
                    ▼
             model_v2.joblib
```

Dane historyczne są wykorzystywane do trenowania i ewaluacji modelu.

PM10 i PM2.5 pozostają osobnymi obserwacjami również podczas przygotowywania danych treningowych.


### 4.2. Przepływ prognozy bieżącej

Użytkownik wybiera stację.

System przygotowuje następnie niezależnie dane dla PM10 i PM2.5.

```text
              Użytkownik
                  │
                  ▼
          wybór jednej stacji
                  │
          ┌───────┴───────┐
          │               │
          ▼               ▼
        PM10            PM2.5
          │               │
          ▼               ▼
   sensory PM10      sensory PM2.5
          │               │
          ▼               ▼
   wybór sensora     wybór sensora
   z najświeższymi   z najświeższymi
       danymi            danymi
          │               │
          └───────┬───────┘
                  ▼
        aktualizacja pomiarów
                  │
          ┌───────┴───────┐
          │               │
          ▼               ▼
    GIOŚ archive      GIOŚ current
          │               │
          └───────┬───────┘
                  ▼
            measurements
                  │
                  ▼
          daily_measurements
                  │
          ┌───────┴───────┐
          │               │
          ▼               ▼
      cechy PM10       cechy PM2.5
          │               │
          └───────┬───────┘
                  │
                  │
          Open-Meteo forecast
                  │
                  ▼
     temperatura / wiatr / wilgotność
                  │
          ┌───────┴───────┐
          ▼               ▼
     model dla PM10   model dla PM2.5
          │               │
          ▼               ▼
    forecast PM10    forecast PM2.5
          │               │
          ▼               ▼
       alarm             alarm
          │               │
          ▼               ▼
    fresh / stale    fresh / stale
          │               │
          └───────┬───────┘
                  ▼
          odpowiedź API
                  │
                  ▼
          PM10 + PM2.5
```

PM10 i PM2.5 są pobierane, agregowane i prognozowane niezależnie.

Połączenie obu wyników następuje dopiero na poziomie odpowiedzi API.

Dla każdego parametru system wybiera najświeższe dostępne dane. Jeżeli aktualny endpoint GIOŚ nie udostępnia pomiarów dla danego sensora, wykorzystywane są najnowsze dane możliwe do uzyskania z pozostałych dostępnych źródeł.

Jeżeli najnowsze dane mają więcej niż 2 dni, prognoza nadal może zostać wykonana, ale zostaje oznaczona jako oparta na starszych danych.

Prognoza pogody Open-Meteo jest pobierana dla kolejnego dnia i wykorzystywana wyłącznie jako wejście modelu.

Użytkownik otrzymuje jedną odpowiedź dla wybranej stacji zawierającą:

- prognozę PM10,
- flagę alarmu PM10,
- informację o aktualności danych PM10,
- prognozę PM2.5,
- flagę alarmu PM2.5,
- informację o aktualności danych PM2.5.