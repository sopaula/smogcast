# Raport modelu

## 1. Cel

Moduł prognozowania SmogCast przewiduje stężenia PM10 i PM2.5 na następny dzień dla wybranych stacji pomiarowych w Polsce.

Model wykorzystuje historyczne pomiary zanieczyszczenia powietrza wraz z cechami pogodowymi i kalendarzowymi.

Celem jest nie tylko uzyskanie dobrej średniej dokładności prognoz, ale również dostarczanie użytecznych przewidywań w okresach podwyższonego zanieczyszczenia powietrza.

## 2. Podział danych i strategia ewaluacji

Modele zostały ocenione przy użyciu podziału czasowego danych zamiast losowego podziału train-test.

Dane sprzed `2025-08-20` zostały wykorzystane do trenowania, natomiast dane od `2025-08-20` wykorzystano jako zbiór testowy.

Takie podejście zachowuje chronologiczną kolejność obserwacji i lepiej odzwierciedla rzeczywisty scenariusz prognozowania.

Rozmiary zbiorów:

- liczba rekordów treningowych przed filtrowaniem cech: `23 012`,
- liczba rekordów treningowych po usunięciu brakujących cech: `22 788`,
- liczba rekordów testowych: `11 336`.

Główne metryki ewaluacji:

- **MAE – Mean Absolute Error**, czyli średni bezwzględny błąd prognozy,
- **RMSE – Root Mean Squared Error**, który silniej penalizuje pojedyncze duże błędy.

## 3. Modele bazowe

Przed oceną modeli uczenia maszynowego sprawdzono dwa proste podejścia bazowe.

### Persistence baseline

Model persistence zakłada, że poziom zanieczyszczenia następnego dnia będzie równy wartości z poprzedniego dnia.

Wyniki:

| Metryka | Wynik |
|---|---:|
| MAE | 6.104 |
| RMSE | 9.680 |

### Climatology baseline

Model climatology przewiduje historyczną średnią miesięczną dla danej stacji i rodzaju zanieczyszczenia, wyliczoną wyłącznie na danych treningowych.

Wyniki:

| Metryka | Wynik |
|---|---:|
| MAE | 8.074 |
| RMSE | 12.414 |

Persistence baseline uzyskał lepsze wyniki i został wykorzystany jako główny punkt odniesienia dla modeli uczenia maszynowego.

## 4. Modele uczenia maszynowego

Przetestowano dwa główne modele:

- Linear Regression,
- Random Forest.

Wyniki na czasowym zbiorze testowym:

| Model | MAE | RMSE |
|---|---:|---:|
| Persistence | 6.104 | 9.680 |
| Climatology | 8.074 | 12.414 |
| Linear Regression | 5.693 | 8.468 |
| Random Forest | 5.599 | 8.843 |

Oba modele uczenia maszynowego uzyskały lepsze wyniki niż modele bazowe.

Random Forest osiągnął najniższy MAE, natomiast Linear Regression uzyskała nieco niższy RMSE.

Oznacza to, że Random Forest miał niższy przeciętny błąd bezwzględny, natomiast Linear Regression lepiej radziła sobie z częścią dużych pojedynczych błędów.

## 5. Wybrany model produkcyjny

Jako model produkcyjny wybrano Random Forest.

Główne wyniki ewaluacji:

| Model | MAE | RMSE |
|---|---:|---:|
| Random Forest | 5.599 | 8.843 |
| Persistence baseline | 6.104 | 9.680 |
| Global mean baseline | 10.200 | 14.625 |

Model osiągnął więc lepsze wyniki zarówno od persistence baseline, jak i prostego modelu przewidującego globalną średnią.

Prognozy wykazywały również wyraźną zmienność:

- odchylenie standardowe prognoz: `13.437`,
- minimalna prognoza: `3.116`,
- maksymalna prognoza: `120.859`,
- liczba unikalnych prognoz: `11 336`.

Potwierdza to, że model nie zwraca jedynie stałej lub średniej wartości.

## 6. Ewaluacja sezonowa

Model został również oceniony oddzielnie dla każdej pory roku.

| Pora roku | N | MAE modelu | RMSE modelu | MAE Persistence | RMSE Persistence |
|---|---:|---:|---:|---:|---:|
| Zima | 2 861 | 9.716 | 14.168 | 10.564 | 15.131 |
| Wiosna | 2 916 | 5.250 | 7.575 | 5.819 | 8.751 |
| Lato | 2 658 | 2.797 | 3.815 | 2.985 | 4.212 |
| Jesień | 2 901 | 4.456 | 6.049 | 4.849 | 6.864 |

Random Forest uzyskał lepsze wyniki od persistence baseline w każdej porze roku.

Największe błędy występowały zimą, natomiast najmniejsze latem.

Jest to zgodne z większą zmiennością stężeń zanieczyszczeń w sezonie grzewczym.

## 7. Analiza błędów

Przeprowadzono bardziej szczegółowe porównanie Random Forest i Linear Regression w celu zbadania największych błędów oraz zachowania modeli w trudniejszych warunkach.

Po uzupełnieniu bazy o dodatkowe obserwacje zbiór ewaluacyjny zwiększył się nieznacznie do `11 364` rekordów.

Wyniki pozostały praktycznie bez zmian:

| Model | MAE | RMSE |
|---|---:|---:|
| Random Forest | 5.596 | 8.836 |
| Linear Regression | 5.691 | 8.463 |

Random Forest nadal osiągał niższy MAE, natomiast Linear Regression zachowała niższy RMSE.

### Największe błędy prognoz

Oddzielnie przeanalizowano 5% prognoz z największym błędem.

| Model | 95. percentyl błędu bezwzględnego | Średni błąd bezwzględny w najgorszych 5% |
|---|---:|---:|
| Random Forest | 17.132 | 27.376 |
| Linear Regression | 16.059 | 25.355 |

Linear Regression generowała mniejsze błędy wśród najtrudniejszych obserwacji.

Wyjaśnia to jej niższy RMSE pomimo nieco gorszego ogólnego MAE.

### Wyniki zimą

Zima była najtrudniejszą porą roku dla modelu.

| Model | MAE zimą | RMSE zimą |
|---|---:|---:|
| Random Forest | 9.716 | 14.168 |
| Linear Regression | 8.990 | 12.905 |

Linear Regression uzyskała lepsze wyniki od Random Forest dla obu metryk w okresie zimowym.

## 8. Wyniki dla wysokich stężeń zanieczyszczeń

Ponieważ SmogCast służy do prognozowania jakości powietrza, szczególnie istotne jest zachowanie modelu podczas epizodów wysokiego zanieczyszczenia.

Dla obserwacji należących do najwyższych 10% rzeczywistych stężeń:

- średni błąd ze znakiem Random Forest: `-8.264 µg/m³`,
- średni błąd ze znakiem Linear Regression: `-11.428 µg/m³`,
- Random Forest zaniżał rzeczywiste stężenie w `76.5%` przypadków,
- Linear Regression zaniżała rzeczywiste stężenie w `81.9%` przypadków.

Oba modele wykazują więc wyraźną tendencję do zaniżania wysokich poziomów zanieczyszczenia.

Random Forest radzi sobie w tym obszarze lepiej, ponieważ jego ujemny bias jest mniejszy i rzadziej zaniża wysokie wartości.

### Wysokie stężenia PM10

Za wysokie wartości PM10 przyjęto najwyższe 10% obserwacji PM10.

Próg:

`41.710 µg/m³`

Liczba obserwacji:

`570`

| Model | Średni błąd ze znakiem | Odsetek zaniżonych prognoz |
|---|---:|---:|
| Random Forest | -10.671 | 79.3% |
| Linear Regression | -13.595 | 83.3% |

Oba modele często zaniżają wysokie wartości PM10, jednak Random Forest wykazuje mniejszy ujemny bias.

### Wysokie stężenia PM2.5

Za wysokie wartości PM2.5 przyjęto najwyższe 10% obserwacji PM2.5.

Próg:

`31.542 µg/m³`

Liczba obserwacji:

`567`

| Model | Średni błąd ze znakiem | Odsetek zaniżonych prognoz |
|---|---:|---:|
| Random Forest | -5.302 | 72.0% |
| Linear Regression | -8.878 | 80.1% |

Taka sama tendencja występuje dla PM2.5.

Random Forest również zaniża wysokie stężenia, ale robi to słabiej i rzadziej niż Linear Regression.

## 9. Ostateczny wybór modelu

Żaden z modeli nie był jednoznacznie najlepszy we wszystkich aspektach.

Linear Regression:

- osiągnęła niższy ogólny RMSE,
- generowała mniejsze błędy w najgorszych 5% przypadków,
- lepiej działała zimą.

Random Forest:

- osiągnął niższy ogólny MAE,
- słabiej zaniżał wysokie wartości PM10 i PM2.5,
- rzadziej zaniżał wysokie stężenia.

Random Forest został więc pozostawiony jako model produkcyjny, ponieważ zachowanie podczas epizodów wysokiego zanieczyszczenia uznano za szczególnie istotne dla zastosowania SmogCast.

## 10. Cechy wejściowe

Model wykorzystuje historyczne wartości PM oraz cechy pochodne związane z czasem.

Cechy dotyczące historycznych poziomów zanieczyszczenia:

- wartość PM z poprzedniego dnia,
- średnia krocząca z 3 dni,
- średnia krocząca z 7 dni.

Cechy kalendarzowe:

- miesiąc,
- dzień tygodnia,
- informacja o weekendzie,
- informacja o sezonie grzewczym.

Zmienne pogodowe:

- temperatura,
- prędkość wiatru,
- wilgotność względna.

Cechy oparte na opóźnieniach i średnich kroczących PM zostały sprawdzone pod kątem target leakage.

Potwierdzono, że:

- `pm_lag_1d` wykorzystuje wartość PM z poprzedniego dnia,
- `pm_mean_3d` wykorzystuje wyłącznie wcześniejsze obserwacje,
- `pm_mean_7d` wykorzystuje wyłącznie wcześniejsze obserwacje.

Wartość PM z dnia będącego celem prognozy nie jest więc używana jako cecha wejściowa.

## 11. Ograniczenie dotyczące danych pogodowych

Podczas analizy target leakage zidentyfikowano ważne ograniczenie metodologiczne.

W czasie trenowania i ewaluacji modelu cechy pogodowe są łączone z danymi dla tego samego dnia, dla którego przewidywane jest stężenie zanieczyszczeń.

Oznacza to, że podczas ewaluacji używana jest rzeczywista historyczna pogoda z dnia docelowego.

W rzeczywistym scenariuszu prognozowania na następny dzień prawdziwa pogoda dla tego dnia nie jest jeszcze znana.

Aplikacja produkcyjna musi więc korzystać z prognozy pogody dostępnej wcześniej.

Powoduje to różnicę pomiędzy warunkami trenowania i ewaluacji a rzeczywistym scenariuszem produkcyjnym.

Wyniki ewaluacji offline mogą przez to być nieco bardziej optymistyczne niż rzeczywista skuteczność modelu.

Lepsza przyszła ewaluacja powinna wykorzystywać historyczne prognozy pogody, jeśli odpowiednie dane będą dostępne.

## 12. Eksperyment z cechami coverage

Przetestowano trzecią wersję modelu zawierającą dodatkowe cechy opisujące kompletność pomiarów:

- `coverage_lag_1d`,
- `coverage_mean_3d`,
- `coverage_mean_7d`.

Cechy te opisują, jak kompletne były dobowe pomiary PM.

Wyniki:

| Model | Wersja | MAE | RMSE |
|---|---|---:|---:|
| Linear Regression | v2 | 5.693 | 8.468 |
| Linear Regression | v3 | 5.752 | 8.532 |
| Random Forest | v2 | 5.599 | 8.843 |
| Random Forest | v3 | 5.617 | 8.890 |

Dodanie cech coverage nie poprawiło wyników ewaluacji.

Model v2 pozostał więc lepszą wersją produkcyjną, natomiast informacja o coverage została zachowana wyłącznie jako wskaźnik jakości danych.

## 13. Ograniczenia

Model prognozujący posiada kilka istotnych ograniczeń.

### Wysokie stężenia zanieczyszczeń

Oba testowane modele mają tendencję do zaniżania wysokich wartości PM10 i PM2.5.

Jest to szczególnie ważne, ponieważ epizody wysokiego zanieczyszczenia należą do najbardziej istotnych sytuacji z perspektywy użytkownika.

Random Forest radzi sobie w tym zakresie lepiej niż Linear Regression, ale problem zaniżania nadal pozostaje.

### Wyniki zimą

Błędy prognoz są znacząco wyższe zimą niż w pozostałych porach roku.

Zimowe stężenia PM są bardziej zmienne i osiągają bardziej ekstremalne wartości, przez co trudniej je dokładnie przewidywać.

### Różnica danych pogodowych

Podczas ewaluacji wykorzystywana jest rzeczywista historyczna pogoda, natomiast w produkcji model korzysta z prognozy pogody.

Wyniki ewaluacji offline mogą być więc nieco bardziej optymistyczne niż rzeczywiste wyniki produkcyjne.

### Ograniczony zestaw zmiennych

Model nie wykorzystuje bezpośrednio części czynników mogących wpływać na poziom zanieczyszczenia, takich jak:

- natężenie ruchu,
- lokalne źródła emisji,
- działalność przemysłowa,
- sposób ogrzewania budynków,
- bardziej szczegółowe warunki atmosferyczne,
- nagłe lokalne zdarzenia.

### Ograniczony zasięg przestrzenny

Obecna wersja SmogCast wykorzystuje 16 wybranych stacji pomiarowych w Polsce.

Model nie został więc oceniony jako uniwersalny model dla wszystkich stacji GIOŚ.

### Zależność od zewnętrznych źródeł danych

Aplikacja zależy od dostępności i jakości danych GIOŚ oraz Open-Meteo.

Brakujące, opóźnione lub niekompletne dane wejściowe mogą obniżyć jakość prognoz.

### Nieaktualne pomiary

Jeżeli najnowsze pomiary PM są starsze niż oczekiwano, aplikacja nadal może wyliczyć prognozę na podstawie istniejących danych, jednak może być ona mniej wiarygodna.

System udostępnia więc informacje o świeżości danych i ostrzega użytkownika, gdy wykorzystywane są starsze obserwacje.

### Dostępność prognozy pogody

Prognozy pogody na następny dzień wykorzystywane przez model produkcyjny są standardowo pobierane podczas zaplanowanego procesu aktualizacji i przechowywane w bazie dla odpowiedniej daty docelowej.

Zapytania o prognozę PM korzystają z zapisanej prognozy pogody zamiast kontaktować się z Open-Meteo podczas normalnego działania.

Jeżeli wymagana prognoza pogody nie istnieje w bazie, Open-Meteo może zostać wykorzystane jako fallback, a pobrany wynik zostaje zapisany.

Pozwala to zmniejszyć czas generowania prognozy oraz zależność od dostępności zewnętrznego API podczas zapytań użytkowników.

Tymczasowe problemy Open-Meteo podczas procesu aktualizacji mogą jednak nadal uniemożliwić pobranie części prognoz pogodowych.

## 14. Wnioski

Końcowy model Random Forest osiąga lepsze wyniki od prostych modeli persistence i climatology oraz zapewnia użyteczne prognozy PM10 i PM2.5 na następny dzień.

Jego największą przewagą nad Linear Regression jest zachowanie podczas epizodów wysokiego zanieczyszczenia, gdzie wykazuje mniejszą tendencję do zaniżania rzeczywistych stężeń.

Jednocześnie ewaluacja pokazuje, że model nie jest równie dokładny we wszystkich warunkach.

Najważniejsze ograniczenia to:

- wyższe błędy zimą,
- zaniżanie wysokich poziomów zanieczyszczeń,
- różnica pomiędzy rzeczywistą pogodą używaną podczas ewaluacji a prognozą pogody dostępną w produkcji,
- zależność od jakości i świeżości zewnętrznych danych.

Z tego powodu prognozy SmogCast powinny być traktowane jako szacunkowe wartości wspierające monitoring jakości powietrza, a nie jako dokładne przewidywania przyszłych stężeń zanieczyszczeń.