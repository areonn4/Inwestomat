from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import logger
from src.load_service import build_run_metadata, save_processed_data
from src.pipeline_cli import parse_pipeline_parameters
from src.transform_service import build_portfolio_report


def main() -> None:
    parameters = parse_pipeline_parameters(
        "Zapis przetworzonego raportu portfela do Parquet i metadanych JSON."
    )
    dataframe = build_portfolio_report(parameters=parameters)
    metadata = build_run_metadata(parameters=parameters, dataframe=dataframe)
    parquet_path, metadata_path = save_processed_data(dataframe=dataframe, metadata=metadata)

    logger.info("Etap load zakończony.")
    logger.info("Parquet: %s", parquet_path)
    logger.info("Metadata: %s", metadata_path)


if __name__ == "__main__":
    main()
