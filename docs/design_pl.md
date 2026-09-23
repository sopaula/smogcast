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

`coverage` określa, jaka część doby posiada poprawne pomiary.

Przykładowo:
- 24 poprawne pomiary oznaczają `100%`,
- 12 poprawnych pomiarów oznacza `50%`,
- 6 poprawnych pomiarów oznacza `25%`.

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


## 4. Inicjalizacja i aktualizacja danych

### Pierwsza inicjalizacja bazy

Do pierwszego uruchomienia służy:

`scripts/init_db.py`

Skrypt wykonuje kolejno:

1. tworzenie tabel SQLite,
2. pobranie i zapis metadanych stacji oraz sensorów,
3. import historycznych pomiarów GIOŚ,
4. import historycznych danych pogodowych Open-Meteo,
5. utworzenie agregatów dobowych.

Przepływ pierwszego uruchomienia:

    pusta baza
        │
        ▼
    create_tables()
        │
        ▼
    metadata
        │
        ▼
    historyczne PM + pogoda
        │
        ▼
    daily_measurements
        │
        ▼
    baza gotowa do pracy

Po inicjalizacji dalsze aktualizacje wykonuje:

`scripts/refresh_all.py`

### Standardowa aktualizacja

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

Jeżeli wykryta zostanie starsza luka w danych, wykorzystywany jest endpoint archiwalny.

Połączenia HTTP korzystają ze wspólnego `httpx.Client`, dzięki czemu połączenia mogą być ponownie wykorzystywane.

Po zapisaniu nowych danych przeliczane są agregaty dobowe dla sensorów, w których pojawiły się nowe pomiary.

Upsert pomiarów wykorzystuje kombinację:

`(sensor_id, timestamp)`

Jeżeli GIOŚ ponownie zwróci ten sam pomiar z poprawioną wartością, istniejący rekord zostaje zaktualizowany zamiast utworzenia duplikatu.

Mechanizm ten został objęty testem.


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

### Standardowy przebieg

Przykładowy pomiar dla 16 stacji po pełnej inicjalizacji bazy:

| Metryka | Wynik |
|---|---:|
| Czas całkowity | 13,09 s |
| Zapytania HTTP | 49 |
| Zapytania bieżące | 43 |
| Zapytania archiwalne | 6 |
| Pobrane rekordy | 1540 |
| Nowe rekordy | 6 |
| Czas danych bieżących | 5,31 s |
| Czas danych archiwalnych | 4,51 s |
| Czas zapisu do bazy | 0,02 s |
| Czas agregacji | 0,09 s |

Część czasu całkowitego wynika również z celowych przerw między zapytaniami archiwalnymi.

Dla 6 zapytań archiwalnych, przy przerwie `0,5 s`, daje to około 3 dodatkowych sekund.

### Zapytania archiwalne

W standardowym przebiegu 6 zapytań archiwalnych dotyczy sensorów, dla których ostatnie dostępne pomiary są znacznie starsze niż zakres danych bieżących.

System wykrywa dla nich lukę i próbuje ją uzupełnić przez endpoint archiwalny.

Jeżeli GIOŚ nie udostępnia nowszych danych dla danego sensora, ostatnia data pozostaje bez zmian i przy kolejnym odświeżeniu może zostać wykonana ponowna próba.

### Pierwszy refresh po inicjalizacji

Pierwszy refresh po zbudowaniu bazy od zera był znacznie dłuższy, ponieważ system musiał uzupełnić większe luki historyczne.

Wynik:

| Metryka | Wynik |
|---|---:|
| Czas całkowity | 296,68 s |
| Zapytania HTTP | 112 |
| Zapytania bieżące | 43 |
| Zapytania archiwalne | 69 |
| Użycia archiwum | 32 |
| Pobrane rekordy | 19050 |
| Nowe rekordy | 19023 |
| Agregaty dobowe | 34353 |

Kolejny przebieg wrócił do normalnego trybu aktualizacji:

| Metryka | Wynik |
|---|---:|
| Czas całkowity | 13,09 s |
| Zapytania HTTP | 49 |
| Zapytania archiwalne | 6 |
| Nowe rekordy | 6 |
| Błędy | 0 |

Potwierdza to stabilne zachowanie procesu po pierwszym uzupełnieniu danych.


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

Wykorzystywane cechy modelu produkcyjnego:

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


## 8. Coverage i model v3

Pokrycie doby (`coverage`) jest liczone i przechowywane w tabeli `daily_measurements`.

Przetestowano również eksperymentalny model v3, który wykorzystywał dodatkowe cechy:

- `coverage_lag_1d`,
- `coverage_mean_3d`,
- `coverage_mean_7d`.

Celem było przekazanie modelowi informacji o tym, czy średnia dobowa została policzona na podstawie pełnej doby, czy tylko części dostępnych pomiarów.

Wyniki modelu v3:

| Model | MAE | RMSE |
|---|---:|---:|
| Linear Regression | 5,752 | 8,532 |
| Random Forest | 5,617 | 8,890 |

Porównanie z modelem v2:

| Model | Wersja | MAE | RMSE |
|---|---|---:|---:|
| Linear Regression | v2 | 5,693 | 8,468 |
| Linear Regression | v3 | 5,752 | 8,532 |
| Random Forest | v2 | 5,599 | 8,843 |
| Random Forest | v3 | 5,617 | 8,890 |

Dodanie informacji o coverage nie poprawiło wyników w obecnym eksperymencie.

Model v3 został zachowany jako wersja eksperymentalna, natomiast model v2 pozostaje modelem produkcyjnym.


## 9. Świeżość danych

Jeżeli najnowszy pomiar ma maksymalnie 2 dni, dane otrzymują status:

`fresh`

Jeżeli dane są starsze, otrzymują status:

`stale`

Prognoza nadal może zostać wykonana, ale użytkownik otrzymuje ostrzeżenie o wykorzystaniu starszych danych.


## 10. Obsługa czasu

Dane pomiarowe GIOŚ są normalizowane do UTC przed zapisem do bazy.

Dla danych zapisanych w czasie lokalnym wykorzystywana jest strefa:

`Europe/Warsaw`

Dzięki temu system uwzględnia:

- czas zimowy CET,
- czas letni CEST,
- zmianę czasu w marcu,
- zmianę czasu w październiku.

Zarówno dane bieżące, jak i archiwalne przechodzą przez wspólną funkcję przygotowującą rekordy do zapisu.

Historyczne dane z plików parquet są również konwertowane z czasu lokalnego do UTC.

W przypadku niejednoznacznych timestampów występujących przy zmianie czasu z letniego na zimowy rekord jest pomijany zamiast arbitralnego przypisywania jednej z dwóch możliwych godzin.


## 11. Model i cache

Produkcyjny model zapisany jest w:

`models/model_v2.joblib`

Model jest przechowywany w pamięci aplikacji, dzięki czemu nie musi być ponownie ładowany przy każdym zapytaniu.

System sprawdza czas modyfikacji pliku modelu.

Jeżeli po ponownym treningu plik zostanie zmieniony, przy kolejnej prognozie automatycznie ładowana jest nowa wersja modelu.

Jeżeli plik się nie zmienił, model jest pobierany z cache.

Mechanizm został objęty testem.

Dodatkowo istnieje eksperymentalny:

`models/model_v3.joblib`

wykorzystujący cechy związane z pokryciem doby.


## 12. Testy

Projekt posiada testy obejmujące między innymi:

- API,
- cache,
- czyszczenie danych,
- agregację dobową,
- budowanie cech,
- integrację GIOŚ,
- sezon grzewczy,
- upsert,
- cache modelu.

Aktualnie zestaw testów obejmuje 16 testów.

Test upsertu potwierdza, że ponowny zapis pomiaru dla tego samego sensora i timestampu:

- nie tworzy duplikatu,
- aktualizuje istniejącą wartość pomiaru.

Przeprowadzono również pełny test działania od pustej bazy.

Proces inicjalizacji poprawnie utworzył:

- 288 stacji,
- 525 sensorów PM,
- 659680 historycznych pomiarów,
- 421248 rekordów pogodowych,
- 34346 agregatów dobowych.

Następnie wykonano kolejne odświeżenia w celu sprawdzenia stabilności i idempotencji procesu.


## 13. Dashboard

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


## 14. Dalszy rozwój

Kolejnym etapem projektu jest konteneryzacja.

Planowany cel:

- uruchomienie API, dashboardu i procesu aktualizacji w Dockerze,
- automatyczne przygotowanie aplikacji przy pierwszym uruchomieniu,
- zachowanie trwałości danych SQLite,
- możliwość uruchomienia projektu jednym poleceniem.

Docelowe kryterium:

    git clone
        │
        ▼
    docker compose up
        │
        ▼
    działające API + dashboard

Dalsze możliwe ulepszenia:

- automatyczne okresowe uruchamianie updatera,
- ograniczenie ponownych bezskutecznych zapytań archiwalnych,
- dalsza optymalizacja agregacji,
- rozszerzenie zbioru treningowego o większą ilość danych historycznych,
- zwiększenie liczby stacji pomiarowych uwzględnianych w systemie,
- dalsze eksperymenty z cechami modelu,
- poprawa jakości prognoz dla wysokich stężeń PM.