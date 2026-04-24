from __future__ import annotations

import unittest
from datetime import date

import pandas as pd

from src.pipeline_models import build_pipeline_parameters
from src.transform_service import build_daily_rate_frame, calculate_portfolio


class TransformServiceTests(unittest.TestCase):
    @staticmethod
    def _build_parameters():
        return build_pipeline_parameters(
            investment_amount_pln=1000,
            start_date=date(2026, 3, 22),
            holding_period_days=30,
            allocations={"USD": 30, "EUR": 40, "HUF": 30},
            weights_are_percent=True,
        )

    @staticmethod
    def _build_raw_rates(include_huf: bool = True) -> pd.DataFrame:
        business_days = pd.date_range("2026-03-20", "2026-04-21", freq="B")
        currencies = ("USD", "EUR", "HUF") if include_huf else ("USD", "EUR")
        base_rates = {"USD": 3.70, "EUR": 4.28, "HUF": 0.0109}

        rows: list[dict[str, object]] = []
        for idx, business_day in enumerate(business_days):
            for currency in currencies:
                rows.append(
                    {
                        "date": business_day,
                        "currency": currency,
                        "rate": base_rates[currency] + idx * 0.01,
                    }
                )

        return pd.DataFrame(rows)

    def test_build_daily_rate_frame_fills_weekend_and_returns_31_days(self) -> None:
        parameters = self._build_parameters()
        raw_rates = self._build_raw_rates()

        daily_rates = build_daily_rate_frame(raw_rates=raw_rates, parameters=parameters)
        friday_usd_rate = raw_rates.loc[
            (raw_rates["date"] == pd.Timestamp("2026-03-20"))
            & (raw_rates["currency"] == "USD"),
            "rate",
        ].iloc[0]

        self.assertEqual(len(daily_rates), 31)
        self.assertEqual(daily_rates.index.min().date(), parameters.start_date)
        self.assertEqual(daily_rates.index.max().date(), parameters.end_date)
        self.assertAlmostEqual(daily_rates.loc["2026-03-22", "USD"], friday_usd_rate)

    def test_build_daily_rate_frame_rejects_missing_currency(self) -> None:
        parameters = self._build_parameters()
        raw_rates = self._build_raw_rates(include_huf=False)

        with self.assertRaises(ValueError):
            build_daily_rate_frame(raw_rates=raw_rates, parameters=parameters)

    def test_calculate_portfolio_starts_at_invested_amount(self) -> None:
        parameters = self._build_parameters()
        raw_rates = self._build_raw_rates()
        daily_rates = build_daily_rate_frame(raw_rates=raw_rates, parameters=parameters)

        report = calculate_portfolio(daily_rates=daily_rates, parameters=parameters)

        self.assertEqual(report.iloc[0]["day_number"], 0)
        self.assertEqual(report.iloc[-1]["day_number"], 30)
        self.assertAlmostEqual(report.iloc[0]["total_value_pln"], 1000.0, places=6)


if __name__ == "__main__":
    unittest.main()
