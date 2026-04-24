from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import date
from pathlib import Path
from unittest.mock import patch

import requests

from src.extract_service import (
    _date_chunks,
    _has_cached_rates,
    extract_rates,
    init_db,
    load_rates_to_sqlite,
)
from src.pipeline_models import build_pipeline_parameters


class _DummySessionManager:
    def __enter__(self):
        return object()

    def __exit__(self, exc_type, exc, tb):
        return False


class ExtractServiceTests(unittest.TestCase):
    def test_date_chunks_split_long_ranges(self) -> None:
        chunks = list(_date_chunks(date(2026, 1, 1), date(2026, 4, 15)))

        self.assertEqual(len(chunks), 2)
        self.assertEqual(chunks[0][0].isoformat(), "2026-01-01")
        self.assertEqual(chunks[0][1].isoformat(), "2026-04-03")
        self.assertEqual(chunks[1][0].isoformat(), "2026-04-04")
        self.assertEqual(chunks[1][1].isoformat(), "2026-04-15")

    def test_load_rates_to_sqlite_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "rates.db"
            init_db(db_path=db_path)
            load_rates_to_sqlite(
                [
                    ("2026-03-22", "USD", 3.70, "A", "001/A/NBP/2026", "2026-04-24T12:00:00"),
                ],
                db_path=db_path,
            )
            load_rates_to_sqlite(
                [
                    ("2026-03-22", "USD", 3.75, "A", "002/A/NBP/2026", "2026-04-24T12:05:00"),
                ],
                db_path=db_path,
            )

            with closing(sqlite3.connect(db_path)) as connection:
                row = connection.execute(
                    "SELECT COUNT(*), MAX(rate) FROM exchange_rates WHERE currency = 'USD'"
                ).fetchone()

        self.assertEqual(row[0], 1)
        self.assertEqual(row[1], 3.75)

    def test_has_cached_rates_accepts_local_cache_for_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "rates.db"
            init_db(db_path=db_path)
            load_rates_to_sqlite(
                [
                    ("2026-03-15", "USD", 3.70, "A", "001", "2026-04-24T12:00:00"),
                    ("2026-04-18", "USD", 3.75, "A", "002", "2026-04-24T12:00:00"),
                ],
                db_path=db_path,
            )

            result = _has_cached_rates(
                currency="USD",
                start_date=date(2026, 3, 15),
                end_date=date(2026, 4, 24),
                db_path=db_path,
            )

        self.assertTrue(result)

    def test_extract_rates_falls_back_to_sqlite_cache(self) -> None:
        parameters = build_pipeline_parameters(
            investment_amount_pln=1000,
            start_date=date(2026, 3, 25),
            holding_period_days=30,
            allocations={"USD": 30, "EUR": 40, "HUF": 30},
            weights_are_percent=True,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "rates.db"
            init_db(db_path=db_path)
            cached_records = [
                (parameters.buffer_start_date.isoformat(), currency, 1.0, "A", "001", "2026-04-24T12:00:00")
                for currency in parameters.currencies
            ] + [
                ((parameters.end_date.replace(day=18)).isoformat(), currency, 1.1, "A", "002", "2026-04-24T12:05:00")
                for currency in parameters.currencies
            ]
            load_rates_to_sqlite(cached_records, db_path=db_path)

            with patch("src.extract_service._build_retry_session", return_value=_DummySessionManager()):
                with patch(
                    "src.extract_service.fetch_rates_from_nbp",
                    side_effect=requests.RequestException("API down"),
                ):
                    summary = extract_rates(
                        parameters=parameters,
                        refresh_from_api=True,
                        db_path=db_path,
                    )

        self.assertEqual(summary.refreshed_currencies, tuple())
        self.assertEqual(summary.cached_currencies, parameters.currencies)


if __name__ == "__main__":
    unittest.main()
