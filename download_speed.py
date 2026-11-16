import argparse
import math
import sys
import time

from dataclasses import dataclass, field
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

REQUEST_COUNT = 10
CHUNK_SIZE = 64 * 1024
MIB = 1024 * 1024


@dataclass(frozen=True)
class DownloadResult:
    elapsed_seconds: float
    downloaded_bytes: int


@dataclass
class DownloadResults:
    results: list[DownloadResult] = field(default_factory=list)

    @property
    def total_items_count(self) -> int:
        return len(self.results)

    @property
    def total_bytes(self) -> int:
        return sum(item.downloaded_bytes for item in self.results)

    @property
    def total_seconds(self) -> float:
        return sum(item.elapsed_seconds for item in self.results)

    @property
    def average_seconds(self) -> float:
        if not self.total_items_count:
            return 0.0

        return self.total_seconds / self.total_items_count

    @property
    def speed_mib_s(self) -> float:
        if self.total_seconds == 0:
            return 0.0

        return self.total_bytes / MIB / self.total_seconds


def main(argv: list[str] | None = None) -> int:
    """Точка входа."""
    args = _get_args(argv=argv)

    try:
        results = download_speed(
            url=args.url,
            timeout=args.timeout,
        )
    except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
        print(f"Ошибка скачивания: {exc}", file=sys.stderr)
        return 1

    _generate_report(url=args.url, results=results)

    return 0


def download_speed(
    *,
    url: str,
    timeout: float = 30.0,
) -> DownloadResults:
    """Считываем агрументы cmd."""
    return _measure_download(url=url, timeout=timeout)


def _get_args(*, argv: list[str] | None = None):
    """Считываем агрументы cmd."""
    parser = argparse.ArgumentParser(
        description="Скорость скачивания: 10 последовательных HTTP-запросов",
    )

    parser.add_argument(
        "url",
        type=_valid_url,
        help="URL файла (http:// или https://)",
    )
    parser.add_argument(
        "--timeout",
        type=_positive_timeout,
        default=30.0,
        metavar="SECONDS",
        help="таймаут ожидания HTTP-операций в секундах (по умолчанию: 30)",
    )

    return parser.parse_args(argv)


def _positive_timeout(value: str) -> float:
    """Валидируем переданный timeout."""
    try:
        timeout = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("таймаут должен быть числом") from exc

    if not math.isfinite(timeout) or timeout <= 0:
        raise argparse.ArgumentTypeError(
            "таймаут должен быть положительным конечным числом"
        )

    return timeout


def _valid_url(value: str) -> str:
    """Валидируем переданный url."""
    try:
        parsed = urlsplit(value)
        hostname = parsed.hostname
    except ValueError as exc:
        raise argparse.ArgumentTypeError("некорректный URL") from exc

    if parsed.scheme not in ("http", "https") or not hostname:
        raise argparse.ArgumentTypeError(
            "нужен полный URL с http:// или https://"
        )

    return value


def _measure_download(
    *,
    url: str,
    timeout: float,
) -> DownloadResults:
    """Выполняем запросы на URL."""
    results = DownloadResults()
    items = results.results

    headers={
        "User-Agent": "download-speed-check/1.0",
        "Accept-Encoding": "identity",
        "Cache-Control": "no-cache",
    }

    for _ in range(REQUEST_COUNT):
        request = Request(
            url,
            headers=headers,
        )

        start = time.perf_counter()
        downloaded_bytes = 0

        with urlopen(request, timeout=timeout) as response:
            while chunk := response.read(CHUNK_SIZE):
                downloaded_bytes += len(chunk)

        elapsed = time.perf_counter() - start
        items.append(
            DownloadResult(
                elapsed_seconds=elapsed,
                downloaded_bytes=downloaded_bytes,
            ),
        )

    return results


def _generate_report(
    *,
    url: str,
    results: DownloadResults,
) -> None:
    """Выводим информацию о загрузке."""
    total_bytes = results.total_bytes
    average_seconds = results.average_seconds
    speed_mib_s = results.speed_mib_s

    report_msg = (
        f"\nURL: {url}\n"
        f"Запросов: {results.total_items_count} (последовательно)\n"
        f"Среднее время запроса: {average_seconds:.3f} с\n"
        f"Скачано: {total_bytes} Б ({total_bytes / MIB:.2f} МиБ)\n"
        f"Средняя скорость скачивания: {speed_mib_s:.2f} МиБ/с\n"
    )

    print(report_msg)

    return None


if __name__ == "__main__":
    sys.exit(main())
