from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import DB_PATH, logger
from src.extract_service import extract_rates
from src.pipeline_cli import parse_pipeline_parameters


def main() -> None:
    parameters = parse_pipeline_parameters(
        "Pobranie kursów NBP i zapis do lokalnej bazy SQLite."
    )
    summary = extract_rates(parameters=parameters, refresh_from_api=True, db_path=DB_PATH)

    logger.info("Etap extract zakończony.")
    logger.info("SQLite: %s", DB_PATH)
    logger.info("Odświeżone waluty: %s", ", ".join(summary.refreshed_currencies) or "-")
    logger.info("Waluty z cache: %s", ", ".join(summary.cached_currencies) or "-")


if __name__ == "__main__":
    main()
