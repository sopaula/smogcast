import time
from concurrent.futures import ThreadPoolExecutor
from threading import Lock

import smogcast.ingest.gios as gios


# Testuje wspólny limiter zapytań archiwalnych.
def test_shared_archive_rate_limit(monkeypatch):
    interval = 0.05
    start_times = []
    lock = Lock()

    class FakeClient:
        def get(self, url, **kwargs):
            with lock:
                start_times.append(time.monotonic())

            return object()

    monkeypatch.setattr(
        gios,
        "client",
        FakeClient(),
    )

    monkeypatch.setattr(
        gios,
        "MIN_REQUEST_INTERVAL",
        interval,
    )

    monkeypatch.setattr(
        gios,
        "_last_request_time",
        0.0,
    )

    gios.reset_http_metrics()

    def send_request():
        return gios.timed_get(
            "https://example.invalid",
            category="archive",
        )

    with ThreadPoolExecutor(max_workers=3) as pool:
        list(
            pool.map(
                lambda _: send_request(),
                range(3),
            )
        )

    assert len(start_times) == 3

    assert all(
        end - start >= interval - 0.005
        for start, end in zip(
            start_times,
            start_times[1:],
            strict=False,
        )
    )

    metrics = gios.get_http_metrics()

    assert metrics["total_requests"] == 3
    assert metrics["archive_requests"] == 3
