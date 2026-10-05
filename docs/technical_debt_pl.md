# Decyzje techniczne i dług techniczny

## 1. Cel dokumentu

Dokument podsumowuje najważniejsze decyzje techniczne podjęte podczas tworzenia SmogCast, obszary świadomie uproszczone, aktualny dług techniczny oraz możliwe kierunki dalszego rozwoju.

Celem jest udokumentowanie nie tylko tego, co zostało zaimplementowane, ale również tego, co świadomie pozostawiono do późniejszej realizacji.

## 2. Najważniejsze decyzje techniczne

### 2.1. Ograniczona liczba stacji pomiarowych

SmogCast korzysta obecnie z 16 wybranych stacji pomiarowych w Polsce zamiast ze wszystkich dostępnych stacji GIOŚ.

Decyzja ta ograniczyła ilość danych wymagających pobierania, przetwarzania i przechowywania podczas tworzenia projektu.

Ułatwiła również trenowanie modelu, debugowanie oraz wdrożenie aplikacji.

Obecna architektura może zostać w przyszłości rozszerzona o kolejne stacje.

### 2.2. Środowiska SQLite i PostgreSQL

SmogCast obsługuje kilka konfiguracji bazy danych:

- SQLite do szybkiej pracy lokalnej,
- PostgreSQL w lokalnym środowisku Docker Compose,
- Azure Database for PostgreSQL w środowisku produkcyjnym.

SQLite upraszcza szybkie uruchamianie projektu lokalnie i nie wymaga dodatkowej infrastruktury.

Środowisko Docker wykorzystuje PostgreSQL, dzięki czemu zachowanie charakterystyczne dla tej bazy może zostać sprawdzone lokalnie przed wdrożeniem.

Aplikacja wykorzystuje zmienną środowiskową `DATABASE_URL` do wyboru bazy danych i może korzystać z SQLite jako wartości domyślnej, jeśli zmienna nie została ustawiona.

### 2.3. Oddzielenie aktualizacji danych od żądań użytkownika

Proces pobierania danych został oddzielony od ładowania dashboardu oraz generowania prognoz.

Główny proces aktualizacji danych realizowany jest przez:

```text
scripts/refresh_all.py
```

Dzięki temu duże ilości danych nie są pobierane za każdym razem, gdy użytkownik otwiera dashboard lub wykonuje zapytanie o prognozę.

W środowisku produkcyjnym proces aktualizacji wykonywany jest automatycznie raz dziennie przez GitHub Actions.

Pozwala to zmniejszyć czas odpowiedzi aplikacji oraz ograniczyć niepotrzebne wywołania zewnętrznych API.

### 2.4. Codzienna aktualizacja przez GitHub Actions

Do aktualizacji danych produkcyjnych wykorzystano zaplanowany workflow GitHub Actions zamiast utrzymywania dodatkowej stale działającej usługi w Azure.

Upraszcza to architekturę wdrożenia oraz ogranicza liczbę wykorzystywanych usług chmurowych.

Workflow może być również uruchamiany ręcznie.

Aktualizacja uznawana jest za w pełni udaną tylko wtedy, gdy wszystkie wymagane etapy zakończą się poprawnie.

Czas ostatniej udanej aktualizacji zapisywany jest w bazie danych.

### 2.5. Lokalny updater w Docker Compose

W lokalnym środowisku Docker działa usługa `updater`, która okresowo aktualizuje bieżące dane.

Dzięki temu lokalne środowisko Docker nie zależy od GitHub Actions i pozwala przetestować kompletny przepływ aplikacji.

### 2.6. Jeden obraz Docker dla API i dashboardu

API i dashboard korzystają z tego samego obrazu aplikacji.

Do uruchamiania FastAPI oraz Streamlit wykorzystywane są różne komendy.

Zmniejsza to duplikację konfiguracji wdrożeniowej oraz pozwala utrzymywać zależności w jednym obrazie.

Minusem tego rozwiązania jest to, że obraz zawiera zależności wymagane przez oba komponenty, nawet jeśli dany kontener nie wykorzystuje wszystkich z nich.

### 2.7. Skalowanie Azure Container Apps

API oraz dashboard zostały wdrożone jako Azure Container Apps.

Przetestowano możliwość skalowania do zera jako sposób ograniczenia zużycia zasobów chmurowych.

Głównym minusem tego rozwiązania jest dłuższy czas pierwszego zapytania po okresie bezczynności, ponieważ kontener musi zostać ponownie uruchomiony.

Podczas aktywnych testów minimalna liczba replik może być utrzymywana powyżej zera, aby uniknąć opóźnień związanych z cold startem.

Konfiguracja skalowania może być więc dostosowana zależnie od tego, czy ważniejsze są niższe koszty, czy szybsza odpowiedź aplikacji.

### 2.8. Wdrożenie w Azure for Students

Wdrożenie zostało wykonane przy użyciu subskrypcji Azure for Students.

Infrastruktura została skonfigurowana z uwzględnieniem ograniczania kosztów.

Projekt nie zakłada, że wszystkie usługi Azure są bezpłatne. PostgreSQL, Container Registry, Container Apps czy Log Analytics mogą wykorzystywać dostępne środki Azure.

### 2.9. Managed Identity dla dostępu do rejestru

Azure Managed Identity jest używane do umożliwienia Container Apps pobierania obrazów z Azure Container Registry.

Konto administratora ACR zostało wyłączone po zakończeniu konfiguracji wdrożenia.

Pozwala to uniknąć przechowywania nazwy użytkownika i hasła do rejestru w konfiguracji aplikacji.

### 2.10. Sekrety poza repozytorium

Connection string produkcyjnej bazy danych nie jest przechowywany w repozytorium Git.

Jest przechowywany jako sekret środowiska wdrożeniowego i przekazywany przez zmienną:

```text
DATABASE_URL
```

GitHub Actions również korzysta z sekretu repozytorium do połączenia z produkcyjną bazą danych.

Zapobiega to przypadkowemu zapisaniu danych dostępowych w kodzie źródłowym.

### 2.11. Health check i readiness check

Endpoint `/health` służy do podstawowego sprawdzania działania procesu API.

Osobny endpoint `/ready` sprawdza, czy aplikacja jest gotowa do obsługi zapytań, uwzględniając dostępność wymaganych zasobów, takich jak baza danych oraz model.

Środowisko Docker wykorzystuje status API przed uruchomieniem zależnych usług.

Azure Container Apps może również wykorzystywać probe'y do wykrywania niedziałających rewizji aplikacji.

Poprawia to niezawodność uruchamiania systemu i ułatwia monitorowanie jego stanu.

### 2.12. Random Forest jako model produkcyjny

Random Forest został wybrany jako produkcyjny model prognozujący.

Linear Regression uzyskała niższy RMSE oraz lepsze wyniki zimą i dla największych błędów prognoz.

Random Forest został jednak pozostawiony jako model produkcyjny, ponieważ uzyskał niższy ogólny MAE oraz wykazywał mniejszą tendencję do zaniżania wysokich stężeń PM10 i PM2.5.

Ze względu na znaczenie wysokich poziomów zanieczyszczenia w zastosowaniu SmogCast uznano to za istotne kryterium wyboru modelu.

### 2.13. Coverage jako wskaźnik jakości danych

Przetestowano dodatkowe cechy modelu opisujące kompletność pomiarów.

Nie poprawiły one wyników ewaluacji, dlatego nie zostały wykorzystane jako cechy wejściowe modelu produkcyjnego.

Informacja o coverage została jednak zachowana jako wskaźnik jakości danych.

### 2.14. Lokalne środowisko PostgreSQL

Docker Compose zapewnia lokalną bazę PostgreSQL jako alternatywę dla szybkiego trybu SQLite.

Pozwala to przetestować cały przepływ aplikacji z wykorzystaniem tego samego silnika bazy danych, który działa w produkcji.

Możliwe jest dzięki temu sprawdzanie zachowań charakterystycznych dla PostgreSQL, takich jak:

- upserty,
- obsługa konfliktów,
- daty i czasy z timezone,
- inicjalizacja schematu,
- ograniczenia bazy danych.

Zmniejsza to różnice pomiędzy środowiskiem lokalnym i produkcyjnym.

### 2.15. Wersjonowany historyczny dataset

Gotowe historyczne pliki Parquet są udostępniane poprzez wersjonowany GitHub Release.

Obecna wersja datasetu:

```text
data-v1
```

Aplikacja najpierw sprawdza, czy wymagane pliki istnieją lokalnie.

Jeżeli ich nie ma, próbuje pobrać przygotowaną wersję z GitHub Release.

Jeżeli Release jest niedostępny, dane historyczne mogą zostać odbudowane bezpośrednio z GIOŚ i Open-Meteo.

Proces inicjalizacji wygląda więc następująco:

```text
pliki lokalne
    ↓
GitHub Release
    ↓
pełna odbudowa z API
```

Zapewnia to szybki start aplikacji bez utraty możliwości pełnego odtworzenia danych ze źródeł.

### 2.16. Metadane datasetu i weryfikacja integralności

Historyczny dataset posiada metadane zawierające:

- wersję datasetu,
- zakres dat,
- źródła danych,
- strefę czasową,
- wersję przetwarzania,
- liczbę rekordów,
- sumy SHA256.

Metadane przechowywane są w:

```text
data/dataset_metadata.json
```

Pobrane pliki Parquet są weryfikowane przy użyciu SHA256 przed ich wykorzystaniem.

Zmniejsza to ryzyko użycia niekompletnych lub uszkodzonych plików i zwiększa powtarzalność procesu inicjalizacji.

### 2.17. Prognoza pogody zapisywana przed zapytaniem użytkownika

Prognozy pogody na następny dzień są pobierane podczas procesu aktualizacji danych i przechowywane w bazie.

Każdy rekord zawiera m.in.:

- identyfikator stacji,
- datę prognozy,
- temperaturę,
- prędkość wiatru,
- wilgotność,
- czas pobrania danych.

Podczas generowania prognozy PM aplikacja najpierw sprawdza pogodę zapisaną w bazie dla właściwego dnia.

Jeżeli jej nie ma, Open-Meteo może zostać wykorzystane jako fallback, a pobrane dane zostają zapisane w bazie.

Zmniejsza to czas odpowiedzi prognozy i ogranicza zależność od zewnętrznego API podczas zapytania użytkownika.

### 2.18. Wznawialna inicjalizacja bazy

Proces inicjalizacji bazy został podzielony na osobne etapy.

Informacja o ukończonych etapach jest zapisywana w bazie.

Dzięki temu po przerwaniu procesu nie trzeba wykonywać całej inicjalizacji od początku.

## 3. Aktualny dług techniczny

### 3.1. Różnica pomiędzy pogodą w ewaluacji i produkcji

Podczas historycznej ewaluacji modelu wykorzystywana jest rzeczywista pogoda z dnia, dla którego przewidywane jest zanieczyszczenie.

W produkcji rzeczywista pogoda dla kolejnego dnia nie jest jeszcze znana i wykorzystywana jest prognoza pogody.

Powoduje to różnicę pomiędzy warunkami ewaluacji offline i rzeczywistym działaniem systemu.

Wyniki ewaluacji mogą przez to być nieco bardziej optymistyczne niż rzeczywista skuteczność produkcyjna.

Lepsza przyszła ewaluacja powinna korzystać z historycznych prognoz pogody, jeśli takie dane będą dostępne.

### 3.2. Zaniżanie wysokich stężeń zanieczyszczeń

Oba testowane modele mają tendencję do zaniżania wysokich wartości PM10 i PM2.5.

Random Forest radzi sobie w tym obszarze lepiej niż Linear Regression, jednak problem nadal występuje.

Jest to szczególnie istotne, ponieważ epizody wysokiego zanieczyszczenia należą do najważniejszych przypadków dla aplikacji SmogCast.

### 3.3. Jakość prognoz zimą

Największe błędy prognoz występują zimą.

W sezonie grzewczym wartości zanieczyszczeń są bardziej zmienne i mogą osiągać dużo wyższe poziomy niż w pozostałych porach roku.

Obecny model nie odwzorowuje tej zmienności w pełni.

### 3.4. Brak automatycznego retrainingu modelu

Model produkcyjny jest trenowany podczas inicjalizacji, jeśli jego plik nie istnieje.

Nie ma obecnie zaplanowanego automatycznego retrainingu produkcyjnego.

Oznacza to, że model nie uczy się automatycznie na nowych danych pojawiających się w systemie.

W systemie działającym przez dłuższy czas warto byłoby dodać okresowe trenowanie modelu.

### 3.5. Brak automatycznego monitorowania jakości modelu

Aplikacja nie porównuje obecnie zapisanych prognoz z pomiarami, które stają się dostępne później.

Nie ma więc automatycznego mechanizmu wykrywania pogorszenia jakości modelu.

W przyszłości można byłoby wyliczać m.in.:

- MAE,
- RMSE,
- bias,
- skuteczność dla poszczególnych pór roku,
- skuteczność dla wysokich poziomów zanieczyszczeń.

### 3.6. Ograniczona liczba stacji

System działa obecnie dla 16 wybranych stacji.

Zakres ten jest wystarczający dla obecnego projektu, ale system nie został zweryfikowany dla wszystkich stacji GIOŚ.

Rozszerzenie liczby stacji zwiększyłoby zasięg aplikacji, ale wymagałoby dodatkowego przetwarzania danych, testowania oraz ponownej ewaluacji modelu.

### 3.7. Zależność od zewnętrznych API

SmogCast zależy od:

- GIOŚ,
- Open-Meteo.

Tymczasowe awarie API, wolne odpowiedzi lub zmiany struktury odpowiedzi mogą wpływać na proces aktualizacji danych.

Zaimplementowano retry i obsługę błędów, ale chwilowe problemy nadal mogą spowodować niepełne odświeżenie danych.

### 3.8. Jeden wspólny obraz aplikacji

API oraz dashboard korzystają z jednego obrazu Docker.

Upraszcza to wdrożenie, ale powoduje, że obraz jest większy niż dwa osobne obrazy zoptymalizowane pod konkretne komponenty.

W obecnej skali projektu prostota została uznana za ważniejszą od maksymalnej optymalizacji obrazu.

### 3.9. Podstawowy monitoring

Azure Log Analytics jest dostępny, a błędy dziennej aktualizacji mogą być sygnalizowane przez GitHub Actions.

Projekt nie posiada jednak zaawansowanego monitoringu operacyjnego wszystkich elementów systemu.

W przyszłości można byłoby monitorować dodatkowo:

- powtarzające się błędy API,
- niedostępność zewnętrznych API,
- niedziałające rewizje Container Apps,
- nietypowo długie requesty,
- błędy połączenia z bazą,
- błędy ładowania modelu.

Na potrzeby obecnego projektu logi, health checki oraz powiadomienia o błędach workflow zapewniają podstawową obserwowalność systemu.

### 3.10. Publiczna aplikacja bez uwierzytelniania

Dashboard produkcyjny jest dostępny publicznie.

Jest to celowe, ponieważ aplikacja udostępnia wyłącznie publiczne dane dotyczące jakości powietrza i pogody.

Nie zaimplementowano kont użytkowników ani systemu logowania.

Jeżeli w przyszłości pojawiłyby się funkcje prywatne lub administracyjne, należałoby dodać uwierzytelnianie i autoryzację.

### 3.11. Brak własnej domeny

Wersja produkcyjna korzysta z domyślnego adresu Azure Container Apps.

Własna domena nie była wymagana do realizacji funkcjonalności projektu i oznaczałaby dodatkową konfigurację.

### 3.12. Brak testów integracyjnych PostgreSQL w CI

Aplikacja może być testowana lokalnie z PostgreSQL przy użyciu Docker Compose.

GitHub Actions nie uruchamia jednak jeszcze dedykowanych testów integracyjnych PostgreSQL.

Dodanie tymczasowej instancji PostgreSQL do workflow CI pozwoliłoby automatycznie sprawdzać zachowanie bazy przy każdym Pull Requeście.

Testy powinny obejmować m.in.:

- inicjalizację schematu,
- modele SQLAlchemy,
- upserty,
- obsługę konfliktów,
- daty z timezone,
- `InitializationState`,
- przechowywanie prognozy pogody.

### 3.13. Odpowiedzialności podczas uruchamiania aplikacji

Projekt posiada osobne skrypty:

```text
prepare_assets.py
init_db.py
refresh_all.py
run_app.py
```

Środowisko Docker rozdziela te odpowiedzialności pomiędzy osobne usługi.

Szybki lokalny tryb `run_app.py` nadal łączy inicjalizację, aktualizację oraz start aplikacji w jednym skrypcie pomocniczym.

Jest to wygodne podczas developmentu, ale w bardziej rozbudowanym systemie można byłoby rozdzielić te operacje jeszcze wyraźniej.

### 3.14. Ręczne aktualizowanie historycznego datasetu

Przygotowany dataset historyczny jest wersjonowany i przechowywany w GitHub Releases.

Tworzenie nowej wersji datasetu, generowanie checksum oraz publikacja plików Release nadal odbywają się ręcznie.

W obecnym projekcie dataset będzie zmieniany rzadko, dlatego rozwiązanie jest wystarczające.

Przy częstszych aktualizacjach proces mógłby zostać zautomatyzowany.

## 4. Świadomie odłożone decyzje

### Automatyczny retraining

Automatyczne trenowanie wymagałoby określenia:

- częstotliwości retrainingu,
- sposobu walidacji,
- kryteriów zastąpienia modelu,
- wersjonowania modeli,
- rollbacku w przypadku gorszego modelu.

W obecnym projekcie pozostawienie wcześniej zweryfikowanego modelu jest rozwiązaniem prostszym i bezpieczniejszym.

### Obsługa wszystkich stacji GIOŚ

Obsługa wszystkich stacji znacznie zwiększyłaby ilość danych oraz złożoność projektu.

Wybrane 16 stacji jest wystarczające do zaprezentowania pełnego pipeline'u danych i prognozowania.

### Bardziej zaawansowane modele

Bardziej złożone rozwiązania, takie jak gradient boosting, dedykowane modele szeregów czasowych czy sieci neuronowe, nie były wymagane do zaprezentowania procesu prognozowania.

Random Forest i Linear Regression pozwoliły uzyskać sensowne wyniki i przeprowadzić szczegółową analizę błędów.

### Złożona infrastruktura chmurowa

Projekt nie wykorzystuje Kubernetes, kolejek wiadomości ani osobnych mikroserwisów dla każdego etapu przetwarzania.

Architektura została celowo utrzymana na poziomie odpowiednim do skali projektu.

### Uwierzytelnianie

System logowania nie został wdrożony, ponieważ aplikacja prezentuje publiczne dane środowiskowe i nie posiada prywatnych funkcji użytkownika.

### Automatyczna publikacja datasetu

Gotowe datasety są obecnie ręcznie publikowane jako wersjonowane GitHub Releases.

Automatyczny pipeline budowania i publikowania datasetu nie jest wymagany przy obecnej skali projektu.

## 5. Najważniejsze dalsze ulepszenia

Najbardziej użyteczne kolejne usprawnienia to:

1. dodanie testów integracyjnych PostgreSQL do CI,
2. odwzorowanie produkcyjnych warunków pogodowych podczas ewaluacji modelu,
3. poprawa prognoz dla wysokich stężeń PM10 i PM2.5,
4. poprawa jakości prognoz zimowych,
5. implementacja monitorowania jakości modelu,
6. dodanie okresowego retrainingu,
7. rozszerzenie monitoringu i alertów,
8. zwiększenie liczby obsługiwanych stacji,
9. dalsze rozdzielenie inicjalizacji od startu aplikacji,
10. automatyzacja generowania metadanych i publikacji datasetu, jeśli wersje danych będą tworzone częściej.

## 6. Obecna architektura

Aktualna aplikacja posiada osobne warstwy odpowiedzialne za pobieranie, przechowywanie, prognozowanie i prezentację danych.

```text
GIOŚ API ───────────────┐
                        │
                        ├──> zaplanowany refresh
                        │         │
Open-Meteo ─────────────┘         │
                                  ▼
                             PostgreSQL
                                  │
                 ┌────────────────┴────────────────┐
                 │                                 │
             pomiary PM                    prognozy pogody
                 │                                 │
                 └──────────────┬──────────────────┘
                                │
                                ▼
                       generowanie cech
                                │
                                ▼
                            model ML
                                │
                                ▼
                            FastAPI
                                │
                                ▼
                           Streamlit
```

Dane historyczne wykorzystywane podczas inicjalizacji posiadają osobny przepływ:

```text
lokalne pliki Parquet
        │
        ▼
czy pliki istnieją?
   │           │
  tak          nie
   │           │
   │           ▼
   │     GitHub Release data-v1
   │           │
   │      dostępny?
   │        │      │
   │       tak     nie
   │        │      │
   │        │      ▼
   │        │   GIOŚ + Open-Meteo
   │        │   pełna odbudowa
   │        │
   └────────┴──────────> inicjalizacja bazy
```

## 7. Możliwa przyszła architektura

Przyszła wersja projektu mogłaby rozszerzyć aktualną architekturę o monitorowanie jakości modelu oraz automatyczny retraining.

```text
zapisane prognozy
      │
      ├──> późniejsze pomiary
      │
      ▼
monitorowanie modelu
      │
      ├── MAE
      ├── RMSE
      ├── bias
      ├── wyniki zimą
      └── wyniki dla wysokich stężeń
      │
      ▼
decyzja o retrainingu
      │
      ▼
nowy model
      │
      ▼
walidacja
      │
      ├── odrzucenie
      │
      └── wdrożenie
```

Można byłoby również zautomatyzować wersjonowanie datasetów:

```text
GIOŚ + Open-Meteo
        │
        ▼
odbudowa historii
        │
        ▼
walidacja danych
        │
        ▼
metadata + SHA256
        │
        ▼
wersjonowany GitHub Release
```

## 8. Podsumowanie

Obecna wersja SmogCast zapewnia kompletny działający pipeline od przygotowania danych historycznych aż do publicznie wdrożonej aplikacji prognozującej.

Projekt obsługuje:

- szybki lokalny development przy użyciu SQLite,
- pełne lokalne środowisko PostgreSQL w Docker Compose,
- wersjonowany historyczny dataset,
- odbudowę danych ze źródłowych API jako fallback,
- produkcyjną bazę PostgreSQL w Azure,
- automatyczną aktualizację danych produkcyjnych,
- przechowywanie prognoz pogody w bazie,
- FastAPI i Streamlit,
- health i readiness checks,
- CI oraz zaplanowane workflow aktualizacji danych.

Część decyzji została świadomie podjęta w taki sposób, aby system pozostał zrozumiały, łatwy w utrzymaniu i odpowiedni do skali projektu.

Najważniejsze nierozwiązane obszary dotyczą:

- jakości modelu podczas wysokich poziomów zanieczyszczeń,
- błędów prognoz zimowych,
- różnicy pomiędzy rzeczywistą pogodą historyczną wykorzystywaną w ewaluacji a prognozą pogody wykorzystywaną w produkcji,
- braku automatycznego retrainingu,
- braku automatycznego monitorowania jakości modelu.

Ograniczenia te są świadomie rozpoznane i udokumentowane.

Obecną wersję można traktować jako działający prototyp w stylu produkcyjnym z jasno określonymi kierunkami dalszego rozwoju.