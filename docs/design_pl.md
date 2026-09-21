# SmogCast – dokument projektowy

## 1. Cel i architektura

SmogCast to aplikacja do monitorowania i prognozowania jakości powietrza w Polsce.

System wykorzystuje:
- dane pomiarowe GIOŚ,
- dane pogodowe Open-Meteo,
- lokalną bazę SQLite,
- model uczenia maszynowego,
- FastAPI jako backend,
- Streamlit jako dashboard.

Główna architektura:

    GIOŚ
      │
      ▼
    refresh_all.py
      │
      ▼
    SQLite
      │
      ├──────────────► FastAPI ──────────────► Streamlit
      │
      └──────────────► daily_measurements
                               │
                               ▼
                           model ML
                               │
                               ▼
                           forecast

Odświeżanie danych zostało oddzielone od dashboardu i prognozy.

Dashboard oraz endpoint prognozy nie pobierają nowych danych bezpośrednio z GIOŚ, tylko korzystają z danych zapisanych wcześniej w bazie.


## 2. Schemat danych

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
| `param_code` |  | kod parametru, np. `PM10`, `PM2.5` |

Jedna stacja może posiadać wiele sensorów, również więcej niż jeden sensor mierzący ten sam parametr.

Sensory są przechowywane lokalnie w bazie, dzięki czemu nie trzeba pobierać ich z API GIOŚ przy każdym odświeżeniu.

### measurements

Przechowuje surowe pomiary jakości powietrza.

| Kolumna | Typ / rola | Opis |
|---|---|---|
| `id` | PK | identyfikator pomiaru |
| `sensor_id` | FK | identyfikator sensora |
| `timestamp` | UTC | czas wykonania pomiaru |
| `value` | nullable | wartość stężenia w µg/m³ |

Dla kombinacji:

`UNIQUE(sensor_id, timestamp)`

obowiązuje unikalność.

Wartość `NULL` oznacza brak poprawnego pomiaru i nie jest automatycznie zamieniana na `0`.

### weather

Przechowuje historyczne dane pogodowe dla lokalizacji stacji.

| Kolumna | Typ / rola | Opis |
|---|---|---|
| `id` | PK | identyfikator rekordu |
| `station_id` | FK | identyfikator stacji |
| `timestamp` |  | czas pomiaru |
| `temp_c` |  | temperatura |
| `wind_ms` |  | prędkość wiatru |
| `humidity` |  | wilgotność |
| `pressure_hpa` |  | ciśnienie |
| `precip_mm` |  | opad |

Do prognozy wykorzystywane są:
- temperatura,
- prędkość wiatru,
- wilgotność.

Prognoza pogody na kolejny dzień jest pobierana z Open-Meteo.

### daily_measurements

Przechowuje dobowe agregaty pomiarów PM10 i PM2.5.

| Kolumna | Opis |
|---|---|
| `station_id` | identyfikator stacji |
| `param_code` | parametr |
| `date` | dzień |
| `mean_value` | średnia dobowa |
| `max_value` | maksymalna wartość dobowa |
| `coverage` | stopień pokrycia danych |

Forecast korzysta z 7 ostatnich poprawnych agregatów.

Rekordy z `mean_value = NULL` są pomijane.

### predictions

Tabela przewidziana do przechowywania wygenerowanych prognoz.

| Kolumna | Typ / rola | Opis |
|---|---|---|
| `id` | PK | identyfikator prognozy |
| `station_id` | FK | identyfikator stacji |
| `param_code` |  | prognozowany parametr |
| `target_date` |  | dzień prognozy |
| `predicted_value` |  | prognozowane stężenie |
| `model_version` |  | wersja modelu |
| `created_at` |  | czas utworzenia |

Obecnie prognoza jest generowana na żądanie i zwracana przez API.


## 3. Relacje między tabelami

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

Relacje:
- `stations.id -> sensors.station_id`
- `sensors.id -> measurements.sensor_id`
- `stations.id -> weather.station_id`
- `stations.id -> daily_measurements.station_id`
- `stations.id -> predictions.station_id`


## 4. Aktualizacja danych

Za aktualizację odpowiada:

`scripts/refresh_all.py`

Przepływ aktualizacji:

    lista stacji z bazy
            │
            ▼
    sensory PM10 / PM2.5
            │
            ▼
       GIOŚ current
            │
            ▼
    porównanie z ostatnim pomiarem
            │
       ┌────┴────┐
       │         │
    brak luki   starsza luka
       │         │
       │         ▼
       │     GIOŚ archive
       │         │
       └────┬────┘
            ▼
      measurements
            │
            ▼
    daily_measurements

Podczas standardowej aktualizacji wykorzystywany jest endpoint bieżących danych GIOŚ.

System pobiera maksymalnie 100 rekordów w jednym zapytaniu.

Do bazy zapisywane są tylko rekordy nowsze od ostatniego poprawnego pomiaru.

Jeżeli luka jest starsza niż zakres dostępny w endpointzie bieżącym, wykorzystywany jest endpoint archiwalny.

Połączenia HTTP korzystają ze wspólnego `httpx.Client`, dzięki czemu połączenia mogą być ponownie wykorzystywane.

Po zapisaniu nowych danych przeliczane są agregaty dobowe dla sensorów, w których pojawiły się nowe pomiary.


## 5. Metryki aktualizacji

Updater zapisuje informacje diagnostyczne:
- liczbę zapytań HTTP,
- liczbę ponowień,
- liczbę zapytań bieżących i archiwalnych,
- liczbę pobranych rekordów,
- liczbę nowych rekordów,
- czas komunikacji z GIOŚ,
- czas zapisu do bazy,
- czas agregacji,
- czas całkowity.

Przykładowy pomiar dla 16 stacji:

| Metryka | Wynik |
|---|---:|
| Czas całkowity | 10,86 s |
| Zapytania HTTP | 49 |
| Zapytania bieżące | 43 |
| Zapytania archiwalne | 6 |
| Pobrane rekordy | 1592 |
| Nowe rekordy | 6 |
| Czas danych bieżących | 4,61 s |
| Czas danych archiwalnych | 3,13 s |
| Czas zapisu do bazy | < 0,01 s |
| Czas agregacji | 0,06 s |

Największą część czasu stanowi komunikacja z API GIOŚ.


## 6. API

Dashboard komunikuje się wyłącznie z FastAPI.

### GET /stations

Zwraca stacje dostępne w aplikacji.

### GET /stations/{station_id}/measurements

Zwraca historię pomiarów wybranego parametru.

Obsługiwane parametry:
- `param`,
- `date_from`,
- `date_to`.

Dashboard pobiera tylko wybrany zakres historii zamiast całej dostępnej historii.

### GET /stations/{station_id}/latest

Zwraca najnowsze poprawne pomiary PM10 i PM2.5.

Rekordy z `value = NULL` są pomijane.

### GET /stations/{station_id}/forecast

Zwraca prognozę PM10 i PM2.5 na kolejny dzień.

Endpoint nie odświeża danych z GIOŚ.


## 7. Prognoza

Dla każdego parametru system:

1. pobiera najnowszy poprawny pomiar,
2. sprawdza świeżość danych,
3. pobiera 7 ostatnich poprawnych agregatów dobowych,
4. pobiera pogodę na kolejny dzień,
5. buduje cechy wejściowe,
6. wykonuje predykcję,
7. sprawdza próg alarmowy.

Wykorzystywane cechy:
- PM z poprzedniego dnia,
- średnia PM z 3 dni,
- średnia PM z 7 dni,
- miesiąc,
- dzień tygodnia,
- weekend,
- sezon grzewczy,
- temperatura,
- prędkość wiatru,
- wilgotność.

PM10 i PM2.5 są prognozowane niezależnie.

Jeżeli w agregatach dobowych pojawi się `mean_value = NULL`, taki rekord jest pomijany.

Do wykonania prognozy wymagane jest 7 poprawnych wartości dobowych.


## 8. Świeżość danych

Jeżeli najnowszy pomiar ma maksymalnie 2 dni, dane otrzymują status:

`fresh`

Jeżeli dane są starsze, otrzymują status:

`stale`

Prognoza nadal może zostać wykonana, ale użytkownik otrzymuje ostrzeżenie o wykorzystaniu starszych danych.


## 9. Model i cache

Model zapisany jest w:

`models/model_v2.joblib`

Model jest przechowywany w pamięci aplikacji, dzięki czemu nie musi być ponownie ładowany przy każdym zapytaniu.

System sprawdza czas modyfikacji pliku modelu.

Jeżeli po ponownym treningu plik zostanie zmieniony, przy kolejnej prognozie automatycznie ładowana jest nowa wersja modelu.

Jeżeli plik się nie zmienił, model jest pobierany z cache.

Mechanizm został objęty testem.


## 10. Dashboard

Dashboard Streamlit umożliwia:
- wyświetlenie mapy stacji,
- przełączanie PM10 i PM2.5,
- wybór stacji,
- podgląd najnowszych pomiarów,
- prognozę na kolejny dzień,
- historię pomiarów.

Historia może być wyświetlana dla:
- 7 dni,
- 30 dni,
- 90 dni,
- 1 roku.

Wartości są oznaczane kolorami:
- zielony – poziom poniżej progu,
- żółty – wartość zbliżona do progu,
- czerwony – przekroczenie progu.

Dashboard zawiera również:
- stały pasek nagłówka,
- logo SmogCast,
- ikonę aplikacji w karcie przeglądarki,
- informacje o źródłach danych.

Źródła danych:
- GIOŚ – jakość powietrza,
- Open-Meteo – dane meteorologiczne.
