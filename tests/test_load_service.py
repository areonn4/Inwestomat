from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

import pandas as pd

from src.extract_service import ExtractionSummary
from src.load_service import build_run_metadata, load_saved_artifacts, save_processed_data
from src.pipeline_models import build_pipeline_parameters


class LoadServiceTests(unittest.TestCase):
    def test_save_processed_data_roundtrip(self) -> None:
        parameters = build_pipeline_parameters(
            investment_amount_pln=1000,
            start_date=date(2026, 3, 22),
            holding_period_days=30,
            allocations={"USD": 30, "EUR": 40, "HUF": 30},
            weights_are_percent=True,
        )
        index = pd.date_range("2026-03-22", periods=2, freq="D", name="valuation_date")
        dataframe = pd.DataFrame(
            {
                "day_number": [0, 1],
                "total_value_pln": [1000.0, 1005.0],
                "daily_change_pln": [0.0, 5.0],
                "cumulative_change_pln": [0.0, 5.0],
                "daily_return_pct": [0.0, 0.005],
                "cumulative_return_pct": [0.0, 0.005],
                "USD_rate": [3.7, 3.8],
                "EUR_rate": [4.2, 4.3],
                "HUF_rate": [0.011, 0.0111],
                "USD_units": [81.08, 81.08],
                "EUR_units": [95.24, 95.24],
                "HUF_units": [27272.72, 27272.72],
                "USD_value_pln": [300.0, 308.0],
                "EUR_value_pln": [400.0, 409.0],
                "HUF_value_pln": [300.0, 288.0],
            },
            index=index,
        )
        metadata = build_run_metadata(
            parameters=parameters,
            dataframe=dataframe,
            extraction_summary=ExtractionSummary(
                refreshed_currencies=("USD", "EUR", "HUF"),
                cached_currencies=tuple(),
            ),
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            parquet_path = Path(temp_dir) / "portfolio.parquet"
            metadata_path = Path(temp_dir) / "portfolio_metadata.json"

            save_processed_data(
                dataframe=dataframe,
                metadata=metadata,
                parquet_path=parquet_path,
                metadata_path=metadata_path,
            )
            loaded_dataframe, loaded_metadata = load_saved_artifacts(
                parquet_path=parquet_path,
                metadata_path=metadata_path,
            )

        self.assertEqual(len(loaded_dataframe), 2)
        self.assertEqual(loaded_metadata["row_count"], 2)
        self.assertEqual(loaded_metadata["allocations"]["USD"], 30.0)


if __name__ == "__main__":
    unittest.main()
