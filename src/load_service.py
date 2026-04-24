from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from src.config import DB_PATH, METADATA_PATH, PROCESSED_DATA_PATH, logger
from src.extract_service import ExtractionSummary
from src.pipeline_models import PipelineParameters


def build_run_metadata(
    parameters: PipelineParameters,
    dataframe: pd.DataFrame,
    extraction_summary: ExtractionSummary | None = None,
) -> dict[str, Any]:
    first_row = dataframe.iloc[0]
    last_row = dataframe.iloc[-1]

    metadata: dict[str, Any] = {
        **parameters.to_metadata(),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "row_count": int(len(dataframe)),
        "database_path": str(DB_PATH),
        "parquet_path": str(PROCESSED_DATA_PATH),
        "metadata_path": str(METADATA_PATH),
        "start_value_pln": round(float(first_row["total_value_pln"]), 2),
        "final_value_pln": round(float(last_row["total_value_pln"]), 2),
        "total_profit_loss_pln": round(float(last_row["cumulative_change_pln"]), 2),
        "pricing_rule": (
            "Dla weekendów i świąt wykorzystywany jest ostatni dostępny "
            "średni kurs NBP z poprzedniego dnia roboczego."
        ),
    }

    metadata["purchase_rates"] = {
        currency: round(float(first_row[f"{currency}_rate"]), 6)
        for currency in parameters.currencies
    }
    metadata["units_purchased"] = {
        currency: round(float(first_row[f"{currency}_units"]), 6)
        for currency in parameters.currencies
    }

    if extraction_summary is not None:
        metadata["refreshed_currencies"] = list(extraction_summary.refreshed_currencies)
        metadata["cached_currencies"] = list(extraction_summary.cached_currencies)

    return metadata


def save_processed_data(
    dataframe: pd.DataFrame,
    metadata: dict[str, Any],
    parquet_path: Path = PROCESSED_DATA_PATH,
    metadata_path: Path = METADATA_PATH,
) -> tuple[Path, Path]:
    parquet_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)

    dataframe.to_parquet(parquet_path)
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    logger.info("Zapisano Parquet: %s", parquet_path)
    logger.info("Zapisano metadane: %s", metadata_path)

    return parquet_path, metadata_path


def load_saved_artifacts(
    parquet_path: Path = PROCESSED_DATA_PATH,
    metadata_path: Path = METADATA_PATH,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    if not parquet_path.exists():
        raise FileNotFoundError(f"Brak pliku Parquet: {parquet_path}")

    dataframe = pd.read_parquet(parquet_path)
    metadata = {}

    if metadata_path.exists():
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

    return dataframe, metadata
