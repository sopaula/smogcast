## 2. Schemat danych

System wykorzystuje następujące tabele.


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

Informacje o sensorach są przechowywane lokalnie w bazie i nie muszą być pobierane z API GIOŚ przy każdym odświeżeniu danych.

Podczas aktualizacji system wykorzystuje sensory zapisane w bazie i wybiera sensor posiadający najświeższe dostępne dane dla danego parametru.


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

Bieżące dane są pobierane przez osobny proces aktualizujący.

Podczas aktualizacji system zapisuje wyłącznie rekordy nowsze od ostatniego poprawnego pomiaru znajdującego się w bazie.

Jeżeli luka w danych jest większa niż zakres dostępny w endpointzie bieżącym, system uzupełnia brakujące dane przy użyciu endpointu archiwalnego.

Jeżeli bieżący endpoint GIOŚ nie udostępnia danych dla konkretnego sensora, system może wykorzystać najświeższe dane już dostępne w bazie.


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

Agregaty dobowe nie są już przeliczane podczas wykonywania prognozy użytkownika.

Po pobraniu nowych pomiarów osobny proces aktualizujący przelicza agregaty dla sensorów, dla których pojawiły się nowe dane.

Forecast korzysta następnie z gotowych danych zapisanych w tabeli `daily_measurements`.

Pozwala to oddzielić aktualizację danych od obsługi żądania użytkownika i skrócić czas wykonywania prognozy.


### predictions

Tabela została przewidziana do przechowywania prognoz wygenerowanych przez model.

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

Obecnie prognoza jest generowana na żądanie i zwracana przez API. Tabela może zostać wykorzystana w przyszłości do przechowywania historii wykonanych prognoz.


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

Dashboard umożliwia:

- podgląd mapy stacji,
- wybór stacji,
- podgląd ostatnich pomiarów,
- podgląd historii pomiarów,
- uzyskanie prognozy jakości powietrza na kolejny dzień.

Dashboard nie pobiera danych bezpośrednio z API GIOŚ.

Dane o jakości powietrza są wcześniej aktualizowane przez osobny proces i zapisywane w lokalnej bazie.

Dzięki temu odpowiedzi API nie muszą czekać na zewnętrzne zapytania do GIOŚ.

Prognoza dla wybranej stacji zawiera jednocześnie wartości PM10 i PM2.5.

Oba parametry są jednak przetwarzane i prognozowane niezależnie.


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

Endpoint zwraca stacje, dla których w lokalnej bazie znajdują się dane pomiarowe.


### GET /stations/{station_id}/measurements

Zwraca pomiary jakości powietrza dla wybranej stacji.

Metoda:

`GET`

Parametry ścieżki:

- `station_id` – identyfikator stacji.

Parametry zapytania:

- `param` – `PM10` lub `PM25`,
- `date_from` – opcjonalny początek zakresu czasu,
- `date_to` – opcjonalny koniec zakresu czasu.

Przykładowe zapytanie:

`GET /stations/117/measurements?param=PM10`

Endpoint umożliwia pobieranie danych pomiarowych używanych m.in. do prezentacji historii jakości powietrza w dashboardzie.

Dane są odczytywane bezpośrednio z lokalnej bazy.


### GET /stations/{station_id}/latest

Zwraca najnowsze dostępne pomiary PM10 i PM2.5 dla wybranej stacji.

Metoda:

`GET`

Parametry ścieżki:

- `station_id` – identyfikator stacji.

Przykładowe zapytanie:

`GET /stations/117/latest`

Endpoint korzysta wyłącznie z lokalnej bazy danych.

Dla każdego parametru wybierany jest najnowszy rekord posiadający poprawną wartość pomiarową.

Rekordy z `value = NULL` są pomijane.


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
  "forecast_date": "2026-09-18",
  "pm10": {
    "sensor_id": 1234,
    "forecast_value": 41.2,
    "threshold": 50.0,
    "alarm": false,
    "data_date": "2026-09-17",
    "data_age_days": 0,
    "data_status": "fresh",
    "warning": null
  },
  "pm25": {
    "sensor_id": 5678,
    "forecast_value": 18.7,
    "threshold": 25.0,
    "alarm": false,
    "data_date": "2026-09-17",
    "data_age_days": 0,
    "data_status": "fresh",
    "warning": null
  }
}
```

PM10 i PM2.5 są prognozowane niezależnie.

Podczas wykonywania prognozy system nie pobiera nowych danych z GIOŚ.

Dla każdego parametru system:

1. odczytuje z lokalnej bazy najnowszy dostępny pomiar,
2. określa sensor, z którego pochodzi najnowszy pomiar,
3. sprawdza aktualność danych wejściowych,
4. pobiera 7 ostatnich agregatów dobowych,
5. pobiera prognozę pogody na kolejny dzień z Open-Meteo,
6. buduje cechy wejściowe modelu,
7. wykonuje predykcję,
8. sprawdza próg alarmowy,
9. zwraca prognozę wraz z informacją o aktualności danych.

Dla każdego parametru odpowiedź zawiera:

- `sensor_id` – identyfikator sensora, z którego pochodzą najnowsze dane,
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

Dzięki temu system wykorzystuje dane znajdujące się już w bazie i jednocześnie informuje użytkownika o ich aktualności.


## 4. Przepływ danych

System wykorzystuje trzy główne przepływy:

1. przepływ historyczny – służący do przygotowania danych i trenowania modelu,
2. przepływ aktualizacji bieżących danych – służący do regularnego pobierania nowych pomiarów z GIOŚ,
3. przepływ prognozy – służący do wykonywania prognozy dla użytkownika.


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
           PM        Open-Meteo archive
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


### 4.2. Przepływ aktualizacji bieżących danych

Aktualizacja danych została oddzielona od dashboardu i od wykonywania prognozy.

Za pobieranie nowych danych odpowiada osobny proces:

`refresh_all.py`

Proces aktualizuje wszystkie stacje wykorzystywane w Smogcast.

```text
               refresh_all.py
                     │
                     ▼
            lista stacji z bazy
                     │
                     ▼
             sensory PM10/PM2.5
                     │
                     ▼
                GIOŚ current
                     │
                     ▼
          najnowsze rekordy pomiarowe
                     │
                     ▼
      porównanie z ostatnim timestampem
                     │
              ┌──────┴──────┐
              │             │
              │ brak luki   │ starsza luka
              │             │
              ▼             ▼
        zapis nowych     GIOŚ archive
          rekordów           │
              │              ▼
              │       uzupełnienie braków
              │              │
              └───────┬──────┘
                      ▼
                 measurements
                      │
                      ▼
             daily_measurements
                      │
                      ▼
              lokalna baza SQLite
```

Podczas standardowej aktualizacji wykorzystywany jest endpoint bieżących danych GIOŚ.

System pobiera maksymalnie 100 rekordów w jednym zapytaniu.

Do bazy zapisywane są wyłącznie rekordy nowsze niż ostatni poprawny pomiar zapisany dla danego sensora.

Jeżeli ostatni pomiar w bazie jest starszy niż zakres obejmowany przez bieżący endpoint GIOŚ, brakujące dane są uzupełniane przy użyciu endpointu archiwalnego.

Po zapisaniu nowych pomiarów przeliczane są agregaty dobowe dla sensorów, dla których pojawiły się nowe dane.

Aktualizacja nie jest wykonywana w trakcie ładowania dashboardu ani podczas wywołania endpointu prognozy.

Dzięki temu użytkownik nie musi czekać na zakończenie zapytań do GIOŚ.

Proces aktualizacji wszystkich 16 stacji trwał podczas testu około:

`17,53 s`

i zakończył się bez błędów.


### 4.3. Przepływ prognozy bieżącej

Użytkownik wybiera stację w dashboardzie.

System korzysta następnie z danych, które zostały wcześniej zapisane w lokalnej bazie.

```text
                 Użytkownik
                     │
                     ▼
              wybór jednej stacji
                     │
                     ▼
                FastAPI
                     │
                     ▼
               lokalna baza
                     │
             ┌───────┴───────┐
             │               │
             ▼               ▼
           PM10            PM2.5
             │               │
             ▼               ▼
      daily_measurements  daily_measurements
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
         model PM10       model PM2.5
             │               │
             ▼               ▼
       forecast PM10     forecast PM2.5
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
                  dashboard
```

PM10 i PM2.5 są prognozowane niezależnie.

Forecast nie wykonuje odświeżania danych z GIOŚ.

Dane PM są odczytywane wyłącznie z lokalnej bazy.

Dla każdego parametru system wykorzystuje 7 ostatnich agregatów dobowych do obliczenia cech:

- wartość z poprzedniego dnia,
- średnią z 3 dni,
- średnią z 7 dni.

Dodatkowo wykorzystywane są:

- miesiąc,
- dzień tygodnia,
- informacja o weekendzie,
- informacja o sezonie grzewczym,
- temperatura,
- prędkość wiatru,
- wilgotność.

Prognoza pogody Open-Meteo jest pobierana dla kolejnego dnia i wykorzystywana wyłącznie jako wejście modelu.

Model jest wczytywany z pliku:

`models/model_v2.joblib`

i przechowywany w pamięci aplikacji, dzięki czemu nie musi być ponownie ładowany przy każdym zapytaniu o prognozę.

Dla każdego parametru system określa również świeżość danych wejściowych.

Jeżeli najnowsze dane mają maksymalnie 2 dni, otrzymują status:

`fresh`

Jeżeli są starsze niż 2 dni:

`stale`

i użytkownik otrzymuje dodatkowe ostrzeżenie.

Użytkownik otrzymuje jedną odpowiedź dla wybranej stacji zawierającą:

- prognozę PM10,
- identyfikator sensora PM10,
- flagę alarmu PM10,
- informację o aktualności danych PM10,
- prognozę PM2.5,
- identyfikator sensora PM2.5,
- flagę alarmu PM2.5,
- informację o aktualności danych PM2.5.


### 4.4. Przepływ danych do dashboardu

Dashboard komunikuje się wyłącznie z API aplikacji.

Nie wykonuje bezpośrednich zapytań do GIOŚ.

```text
                SQLite
                   │
                   ▼
                FastAPI
                   │
                   ▼
               Streamlit
                   │
        ┌──────────┼──────────┐
        ▼          ▼          ▼
      mapa      pomiary    historia
                               │
                               ▼
                           prognoza
```

Dashboard umożliwia:

- wyświetlenie mapy dostępnych stacji,
- przełączanie widoku PM10 i PM2.5,
- podgląd najnowszych pomiarów,
- podgląd czasu wykonania ostatniego pomiaru,
- wybór konkretnej stacji,
- podgląd prognozy na kolejny dzień,
- podgląd historii pomiarów.

Wartości na dashboardzie są dodatkowo oznaczone kolorami zależnie od poziomu względem progu:

- zielony – wartość wyraźnie poniżej progu,
- żółty – wartość zbliżona do progu,
- czerwony – przekroczenie progu.

Dashboard zawiera również stale widoczną informację o źródłach danych:

- Główny Inspektorat Ochrony Środowiska – dane o jakości powietrza,
- Open-Meteo – dane meteorologiczne.