from __future__ import annotations

import argparse
import unittest
from datetime import date

from src.pipeline_cli import _parse_allocations
from src.pipeline_models import ConfigurationError, build_pipeline_parameters


class PipelineModelsTests(unittest.TestCase):
    def test_build_parameters_accepts_valid_input(self) -> None:
        parameters = build_pipeline_parameters(
            investment_amount_pln=1000,
            start_date=date(2026, 3, 22),
            holding_period_days=30,
            allocations={"USD": 30, "EUR": 40, "HUF": 30},
            weights_are_percent=True,
        )

        self.assertEqual(parameters.currencies, ("USD", "EUR", "HUF"))
        self.assertEqual(parameters.end_date.isoformat(), "2026-04-21")
        self.assertEqual(parameters.allocation_percentages["EUR"], 40.0)

    def test_build_parameters_rejects_future_end_date(self) -> None:
        with self.assertRaises(ConfigurationError):
            build_pipeline_parameters(
                investment_amount_pln=1000,
                start_date=date(2099, 1, 1),
                holding_period_days=30,
                allocations={"USD": 30, "EUR": 40, "HUF": 30},
                weights_are_percent=True,
            )

    def test_build_parameters_rejects_unsupported_currency(self) -> None:
        with self.assertRaises(ConfigurationError):
            build_pipeline_parameters(
                investment_amount_pln=1000,
                start_date=date(2026, 3, 22),
                holding_period_days=30,
                allocations={"USD": 30, "EUR": 40, "BTC": 30},
                weights_are_percent=True,
            )

    def test_build_parameters_rejects_invalid_weight_sum(self) -> None:
        with self.assertRaises(ConfigurationError):
            build_pipeline_parameters(
                investment_amount_pln=1000,
                start_date=date(2026, 3, 22),
                holding_period_days=30,
                allocations={"USD": 30, "EUR": 30, "HUF": 20},
                weights_are_percent=True,
            )

    def test_parse_allocations_rejects_duplicate_currency(self) -> None:
        with self.assertRaises(argparse.ArgumentTypeError):
            _parse_allocations(["USD=30", "EUR=40", "USD=30"])


if __name__ == "__main__":
    unittest.main()
