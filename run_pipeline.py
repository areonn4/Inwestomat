from __future__ import annotations

from src.config import logger
from src.pipeline import run_pipeline
from src.pipeline_cli import parse_pipeline_parameters


def main() -> None:
    parameters = parse_pipeline_parameters(
        "Uruchamia pełny pipeline: extract -> transform -> load."
    )
    result = run_pipeline(parameters=parameters, refresh_from_api=True)

    logger.info("Pipeline zakończony sukcesem.")
    logger.info("Baza SQLite: %s", result.db_path)
    logger.info("Parquet: %s", result.parquet_path)
    logger.info("Metadata: %s", result.metadata_path)


if __name__ == "__main__":
    main()
