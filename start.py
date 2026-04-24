from __future__ import annotations

import argparse
import subprocess
import sys
from typing import Sequence

from src.config import logger
from src.pipeline import run_pipeline
from src.pipeline_cli import parse_pipeline_parameters


def parse_startup_arguments(
    args: Sequence[str] | None = None,
) -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(
        description=(
            "Jeden punkt wejścia do projektu: uruchamia pełny pipeline "
            "i następnie startuje dashboard Streamlit."
        )
    )
    parser.add_argument(
        "--skip-pipeline",
        action="store_true",
        help="Pomiń etap ETL i uruchom tylko dashboard na już zapisanych artefaktach.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8501,
        help="Port dla aplikacji Streamlit.",
    )
    parser.add_argument(
        "--address",
        default="127.0.0.1",
        help="Adres nasłuchiwania Streamlit.",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Uruchom dashboard bez otwierania przeglądarki.",
    )

    return parser.parse_known_args(args=args)


def launch_streamlit(*, port: int, address: str, headless: bool) -> int:
    command = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        "app.py",
        "--server.port",
        str(port),
        "--server.address",
        address,
        "--server.headless",
        "true" if headless else "false",
    ]

    logger.info("Uruchamianie dashboardu Streamlit pod adresem http://%s:%s", address, port)
    logger.info("Polecenie startowe: %s", " ".join(command))

    return subprocess.run(command, check=False).returncode


def main(args: Sequence[str] | None = None) -> int:
    startup_args, pipeline_args = parse_startup_arguments(args=args)

    if not startup_args.skip_pipeline:
        parameters = parse_pipeline_parameters(
            "Pełny start projektu: extract -> transform -> load -> dashboard.",
            args=pipeline_args,
        )
        result = run_pipeline(parameters=parameters, refresh_from_api=True)

        logger.info("Pipeline zakończony sukcesem.")
        logger.info("Baza SQLite: %s", result.db_path)
        logger.info("Parquet: %s", result.parquet_path)
        logger.info("Metadata: %s", result.metadata_path)
    elif pipeline_args:
        logger.warning(
            "Przekazane parametry pipeline zostały zignorowane, ponieważ użyto --skip-pipeline."
        )

    return launch_streamlit(
        port=startup_args.port,
        address=startup_args.address,
        headless=startup_args.headless,
    )


if __name__ == "__main__":
    raise SystemExit(main())
