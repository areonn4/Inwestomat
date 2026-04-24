from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Iterable

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.config import (
    API_TIMEOUT_SECONDS,
    DB_PATH,
    NBP_API_BASE_URL,
    NBP_MAX_DAYS_PER_REQUEST,
    logger,
)
from src.pipeline_models import PipelineParameters


@dataclass(frozen=True, slots=True)
class ExtractionSummary:
    refreshed_currencies: tuple[str, ...]
    cached_currencies: tuple[str, ...]


def init_db(db_path=DB_PATH) -> None:
    logger.info("Inicjalizacja bazy SQLite: %s", db_path)

    with closing(sqlite3.connect(db_path)) as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS exchange_rates (
                date TEXT NOT NULL,
                currency TEXT NOT NULL,
                rate REAL NOT NULL,
                table_name TEXT,
                bulletin_no TEXT,
                fetched_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cursor.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_exchange_rates_date_currency
            ON exchange_rates(date, currency)
            """
        )

        existing_columns = {
            row[1]
            for row in cursor.execute("PRAGMA table_info(exchange_rates)").fetchall()
        }

        if "table_name" not in existing_columns:
            cursor.execute("ALTER TABLE exchange_rates ADD COLUMN table_name TEXT")
        if "bulletin_no" not in existing_columns:
            cursor.execute("ALTER TABLE exchange_rates ADD COLUMN bulletin_no TEXT")
        if "fetched_at" not in existing_columns:
            cursor.execute("ALTER TABLE exchange_rates ADD COLUMN fetched_at TEXT")
            cursor.execute(
                """
                UPDATE exchange_rates
                SET fetched_at = CURRENT_TIMESTAMP
                WHERE fetched_at IS NULL
                """
            )

        connection.commit()


def _build_retry_session() -> requests.Session:
    retry = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
    )
    adapter = HTTPAdapter(max_retries=retry)

    session = requests.Session()
    session.headers.update({"Accept": "application/json"})
    session.mount("https://", adapter)
    return session


def _date_chunks(start_date: date, end_date: date) -> Iterable[tuple[date, date]]:
    chunk_start = start_date

    while chunk_start <= end_date:
        chunk_end = min(
            chunk_start + timedelta(days=NBP_MAX_DAYS_PER_REQUEST - 1),
            end_date,
        )
        yield chunk_start, chunk_end
        chunk_start = chunk_end + timedelta(days=1)


def fetch_rates_from_nbp(
    session: requests.Session,
    currency: str,
    start_date: date,
    end_date: date,
) -> list[tuple[str, str, float, str | None, str | None, str]]:
    all_records: list[tuple[str, str, float, str | None, str | None, str]] = []

    for chunk_start, chunk_end in _date_chunks(start_date, end_date):
        url = (
            f"{NBP_API_BASE_URL}/a/{currency}/"
            f"{chunk_start.isoformat()}/{chunk_end.isoformat()}/?format=json"
        )
        logger.info(
            "Pobieranie kursów %s z NBP dla zakresu %s - %s",
            currency,
            chunk_start.isoformat(),
            chunk_end.isoformat(),
        )

        response = session.get(url, timeout=API_TIMEOUT_SECONDS)

        if response.status_code == 404:
            raise ValueError(f"NBP nie zwraca danych dla waluty {currency}.")

        response.raise_for_status()
        payload = response.json()

        fetched_at = datetime.now().isoformat(timespec="seconds")
        all_records.extend(
            (
                rate_row["effectiveDate"],
                currency,
                float(rate_row["mid"]),
                payload.get("table"),
                rate_row.get("no"),
                fetched_at,
            )
            for rate_row in payload.get("rates", [])
        )

    if not all_records:
        raise ValueError(
            f"NBP nie zwrócił żadnych danych dla {currency} w zadanym zakresie."
        )

    return all_records


def load_rates_to_sqlite(
    records: list[tuple[str, str, float, str | None, str | None, str]],
    db_path=DB_PATH,
) -> None:
    logger.info("Zapisywanie %s rekordów do SQLite", len(records))

    with closing(sqlite3.connect(db_path)) as connection:
        connection.executemany(
            """
            INSERT INTO exchange_rates (
                date,
                currency,
                rate,
                table_name,
                bulletin_no,
                fetched_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(date, currency) DO UPDATE SET
                rate = excluded.rate,
                table_name = excluded.table_name,
                bulletin_no = excluded.bulletin_no,
                fetched_at = excluded.fetched_at
            """,
            records,
        )
        connection.commit()


def _has_cached_rates(
    currency: str,
    start_date: date,
    end_date: date,
    db_path=DB_PATH,
) -> bool:
    with closing(sqlite3.connect(db_path)) as connection:
        row = connection.execute(
            """
            SELECT COUNT(*), MIN(date), MAX(date)
            FROM exchange_rates
            WHERE currency = ?
              AND date BETWEEN ? AND ?
            """,
            (currency, start_date.isoformat(), end_date.isoformat()),
        ).fetchone()

    record_count, min_date, max_date = row
    if record_count == 0 or min_date is None or max_date is None:
        return False

    latest_acceptable_date = end_date - timedelta(days=7)
    return min_date <= start_date.isoformat() and max_date >= latest_acceptable_date.isoformat()


def extract_rates(
    parameters: PipelineParameters,
    *,
    refresh_from_api: bool = True,
    db_path=DB_PATH,
) -> ExtractionSummary:
    init_db(db_path=db_path)

    if not refresh_from_api:
        logger.info("Odświeżanie z API wyłączone. Pipeline użyje danych z bazy.")
        return ExtractionSummary(
            refreshed_currencies=tuple(),
            cached_currencies=parameters.currencies,
        )

    refreshed_currencies: list[str] = []
    cached_currencies: list[str] = []

    with _build_retry_session() as session:
        for currency in parameters.currencies:
            try:
                records = fetch_rates_from_nbp(
                    session=session,
                    currency=currency,
                    start_date=parameters.buffer_start_date,
                    end_date=parameters.end_date,
                )
                load_rates_to_sqlite(records=records, db_path=db_path)
                refreshed_currencies.append(currency)
            except (requests.RequestException, ValueError) as exc:
                if _has_cached_rates(
                    currency=currency,
                    start_date=parameters.buffer_start_date,
                    end_date=parameters.end_date,
                    db_path=db_path,
                ):
                    logger.warning(
                        "Nie udało się odświeżyć %s z API (%s). Używam danych z lokalnej bazy.",
                        currency,
                        exc,
                    )
                    cached_currencies.append(currency)
                    continue

                raise RuntimeError(
                    f"Brak aktualnych danych dla {currency}. "
                    "API nie odpowiedziało i baza lokalna nie ma wystarczającego zakresu."
                ) from exc

    return ExtractionSummary(
        refreshed_currencies=tuple(refreshed_currencies),
        cached_currencies=tuple(cached_currencies),
    )
