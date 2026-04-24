from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import logger
from src.pipeline_cli import parse_pipeline_parameters
from src.transform_service import build_portfolio_report


def main() -> None:
    parameters = parse_pipeline_parameters(
        "Transformacja danych z SQLite do raportu portfela."
    )
    dataframe = build_portfolio_report(parameters=parameters)

    logger.info("Etap transform zakończony.")
    print(dataframe.head().to_string())


if __name__ == "__main__":
    main()
