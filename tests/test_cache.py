from smogcast.ingest import gios


def test_get_station_sensors_uses_cache(monkeypatch):
    calls = []

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "Lista stanowisk pomiarowych dla podanej stacji": [
                    {
                        "Id stanowiska": 123,
                    }
                ]
            }

    def fake_get(*args, **kwargs):
        calls.append(
            (
                args,
                kwargs,
            )
        )

        return FakeResponse()

    # Czyści cache przed testem
    gios._sensors_cache.clear()

    # Podmienia prawdziwe httpx.get
    # na funkcję testową
    monkeypatch.setattr(
        gios.httpx,
        "get",
        fake_get,
    )

    # Pierwsze wywołanie
    # pobiera dane z API
    first_result = gios.get_station_sensors(
        117,
    )

    # Drugie wywołanie
    # powinno użyć cache
    second_result = gios.get_station_sensors(
        117,
    )

    assert first_result == second_result

    # API powinno zostać
    # wywołane tylko raz
    assert len(calls) == 1


def test_get_station_sensors_refreshes_after_ttl(
    monkeypatch,
):
    calls = []

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "Lista stanowisk pomiarowych dla podanej stacji": [
                    {
                        "Id stanowiska": 123,
                    }
                ]
            }

    def fake_get(*args, **kwargs):
        calls.append(
            (
                args,
                kwargs,
            )
        )

        return FakeResponse()

    # Czyści cache przed testem
    gios._sensors_cache.clear()

    # Ustawia kontrolowany czas
    current_time = [1000.0]

    def fake_monotonic():
        return current_time[0]

    monkeypatch.setattr(
        gios.httpx,
        "get",
        fake_get,
    )

    monkeypatch.setattr(
        gios.time,
        "monotonic",
        fake_monotonic,
    )

    # Pierwsze wywołanie
    # pobiera dane z API
    gios.get_station_sensors(
        117,
    )

    # Przesuwamy czas o więcej
    # niż wynosi TTL cache
    current_time[0] += gios.METADATA_CACHE_TTL_SECONDS + 1

    # Cache powinien już wygasnąć,
    # więc dane są pobierane ponownie
    gios.get_station_sensors(
        117,
    )

    # API powinno zostać
    # wywołane dwa razy
    assert len(calls) == 2
