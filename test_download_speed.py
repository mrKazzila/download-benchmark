
import importlib
from urllib.error import URLError

import pytest

app = importlib.import_module("download_speed")


def test_download_results_statistics():
    results = app.DownloadResults(
        results=[
            app.DownloadResult(
                elapsed_seconds=2.0,
                downloaded_bytes=2 * app.MIB,
            ),
            app.DownloadResult(
                elapsed_seconds=4.0,
                downloaded_bytes=4 * app.MIB,
            ),
        ]
    )

    assert results.total_items_count == 2
    assert results.total_bytes == 6 * app.MIB
    assert results.total_seconds == 6.0
    assert results.average_seconds == 3.0
    assert results.speed_mib_s == 1.0


def test_download_results_empty():
    results = app.DownloadResults()

    assert results.total_items_count == 0
    assert results.total_bytes == 0
    assert results.average_seconds == 0.0
    assert results.speed_mib_s == 0.0


def test_download_speed_reads_all_responses(monkeypatch):
    payload = b"Hello, world!"
    active_requests = 0
    request_count = 0
    read_count = 0

    class FakeResponse:
        def __init__(self):
            self.offset = 0

        def __enter__(self):
            nonlocal active_requests
            active_requests += 1
            assert active_requests == 1
            return self

        def __exit__(self, *args):
            nonlocal active_requests
            active_requests -= 1

        def read(self, size):
            nonlocal read_count
            read_count += 1

            chunk = payload[self.offset:self.offset + size]
            self.offset += len(chunk)
            return chunk

    def fake_urlopen(request, timeout):
        nonlocal request_count
        request_count += 1

        assert request.full_url == "https://example.com/file"
        assert timeout == 5.0

        return FakeResponse()

    times = iter(range(0, 20))

    monkeypatch.setattr(app, "urlopen", fake_urlopen)
    monkeypatch.setattr(app.time, "perf_counter", lambda: next(times))
    monkeypatch.setattr(app, "CHUNK_SIZE", 4)

    results = app.download_speed(
        url="https://example.com/file",
        timeout=5.0,
    )

    assert request_count == 10
    assert active_requests == 0
    assert read_count == 50

    assert results.total_items_count == 10
    assert results.total_bytes == len(payload) * 10
    assert results.total_seconds == 10.0
    assert results.average_seconds == 1.0


def test_main_success(monkeypatch, capsys):
    expected = app.DownloadResults(
        results=[
            app.DownloadResult(1.0, app.MIB)
        ]
    )

    def fake_download_speed(*, url, timeout):
        assert url == "https://example.com/file"
        assert timeout == 30.0
        return expected

    monkeypatch.setattr(app, "download_speed", fake_download_speed)

    exit_code = app.main(["https://example.com/file"])
    output = capsys.readouterr()

    assert exit_code == 0
    assert "Среднее время запроса: 1.000 с" in output.out
    assert "Средняя скорость скачивания: 1.00 МиБ/с" in output.out
    assert output.err == ""


def test_main_network_error(monkeypatch, capsys):
    def fake_download_speed(*, url, timeout):
        raise URLError("Connection failed")

    monkeypatch.setattr(app, "download_speed", fake_download_speed)

    exit_code = app.main(["https://example.com/file"])
    output = capsys.readouterr()

    assert exit_code == 1
    assert "Ошибка скачивания" in output.err


@pytest.mark.parametrize(
    "value",
    ["0", "-1", "nan", "inf", "abc"],
)
def test_invalid_timeout(value):
    with pytest.raises(app.argparse.ArgumentTypeError):
        app._positive_timeout(value)
