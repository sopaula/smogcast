# Smogcast MVP

## Cel MVP

Celem Smogcast MVP jest dostarczenie użytkownikowi prostej prognozy
stężenia PM10 i PM2.5 na następny dzień dla wybranej stacji,
na podstawie historycznych danych o jakości powietrza i warunkach pogodowych.

## User stories

1. Jako mieszkaniec chcę sprawdzić prognozę PM10 i PM2.5 na następny dzień dla wybranej stacji, aby lepiej zaplanować aktywność na zewnątrz.

2. Jako mieszkaniec chcę zobaczyć przewidywany poziom zanieczyszczenia w czytelnej formie, aby szybko ocenić jakość powietrza.

3. Jako użytkownik chcę wybrać jedną z dostępnych stacji pomiarowych, aby otrzymać prognozę dla interesującej mnie lokalizacji.

4. Jako użytkownik chcę zobaczyć podstawowe informacje pogodowe powiązane z prognozą, aby lepiej zrozumieć warunki wpływające na jakość powietrza.

5. Jako użytkownik chcę zobaczyć ostatnie dostępne pomiary PM oraz prognozę na kolejny dzień, aby porównać aktualną sytuację z przewidywaną.

## Zakres MVP

### W środku

- prognoza PM10 i PM2.5 na następny dzień
- wybór jednej z obsługiwanych stacji pomiarowych
- wykorzystanie historycznych danych GIOŚ
- wykorzystanie danych pogodowych Open-Meteo
- model predykcyjny oparty na danych historycznych
- prezentacja ostatnich pomiarów i prognozy
- podstawowy backend API
- prosty interfejs użytkownika lub dashboard
- obsługa wybranych stacji z dobrym pokryciem danych
- podstawowa informacja o jakości prognozy modelu

### Świadomie poza MVP

- konto użytkownika i logowanie
- personalizacja profilu użytkownika
- powiadomienia push, e-mail lub SMS
- prognozy dla wszystkich stacji GIOŚ w Polsce
- automatyczne wykrywanie lokalizacji użytkownika
- prognozowanie innych zanieczyszczeń, np. NO2, SO2, O3
- prognoza wielodniowa
- aplikacja mobilna
- interaktywna mapa całej Polski
- zaawansowane alerty zdrowotne
- rekomendacje medyczne
- integracja z prywatnymi czujnikami lub urządzeniami IoT