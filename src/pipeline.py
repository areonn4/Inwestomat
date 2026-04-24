from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from src.config import DB_PATH, METADATA_PATH, PROCESSED_DATA_PATH
from src.extract_service import ExtractionSummary, extract_rates
from src.load_service import build_run_metadata, load_saved_artifacts, save_processed_data
from src.pipeline_models import PipelineParameters
from src.transform_service import build_portfolio_report


@dataclass(slots=True)
class PipelineRunResult:
    data: pd.DataFrame
    metadata: dict[str, Any]
    parquet_path: Path
    metadata_path: Path
    db_path: Path
    extraction_summary: ExtractionSummary


def run_pipeline(
    parameters: PipelineParameters,
    *,
    refresh_from_api: bool = True,
) -> PipelineRunResult:
    extraction_summary = extract_rates(
        parameters=parameters,
        refresh_from_api=refresh_from_api,
        db_path=DB_PATH,
    )
    dataframe = build_portfolio_report(parameters=parameters, db_path=DB_PATH)
    metadata = build_run_metadata(
        parameters=parameters,
        dataframe=dataframe,
        extraction_summary=extraction_summary,
    )
    parquet_path, metadata_path = save_processed_data(
        dataframe=dataframe,
        metadata=metadata,
        parquet_path=PROCESSED_DATA_PATH,
        metadata_path=METADATA_PATH,
    )

    return PipelineRunResult(
        data=dataframe,
        metadata=metadata,
        parquet_path=parquet_path,
        metadata_path=metadata_path,
        db_path=DB_PATH,
        extraction_summary=extraction_summary,
    )


def load_existing_analysis() -> PipelineRunResult | None:
    if not PROCESSED_DATA_PATH.exists():
        return None

    dataframe, metadata = load_saved_artifacts(
        parquet_path=PROCESSED_DATA_PATH,
        metadata_path=METADATA_PATH,
    )

    if dataframe.empty:
        raise ValueError("Zapisany plik Parquet jest pusty.")

    expected_columns = {
        "day_number",
        "total_value_pln",
        "daily_change_pln",
        "cumulative_change_pln",
    }
    missing_columns = sorted(expected_columns.difference(dataframe.columns))
    if missing_columns:
        raise ValueError(
            "Zapisany plik Parquet nie zawiera wymaganych kolumn: "
            f"{', '.join(missing_columns)}."
        )

    expected_row_count = metadata.get("row_count")
    if expected_row_count is not None and int(expected_row_count) != len(dataframe):
        raise ValueError(
            "Niespójność artefaktów: liczba wierszy w Parquet nie zgadza się z metadanymi."
        )

    extraction_summary = ExtractionSummary(
        refreshed_currencies=tuple(metadata.get("refreshed_currencies", [])),
        cached_currencies=tuple(metadata.get("cached_currencies", [])),
    )

    return PipelineRunResult(
        data=dataframe,
        metadata=metadata,
        parquet_path=PROCESSED_DATA_PATH,
        metadata_path=METADATA_PATH,
        db_path=DB_PATH,
        extraction_summary=extraction_summary,
    )
