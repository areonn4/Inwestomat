from __future__ import annotations

import argparse
from datetime import datetime
from typing import Sequence

from src.config import (
    DEFAULT_ALLOCATION,
    DEFAULT_HOLDING_PERIOD_DAYS,
    DEFAULT_INVESTMENT_AMOUNT_PLN,
    DEFAULT_START_DATE,
)
from src.pipeline_models import PipelineParameters, build_pipeline_parameters


def _parse_iso_date(value: str):
    return datetime.strptime(value, "%Y-%m-%d").date()


def _parse_allocations(tokens: Sequence[str]) -> dict[str, float]:
    allocations: dict[str, float] = {}

    for token in tokens:
        if "=" not in token:
            raise argparse.ArgumentTypeError(
                "Alokacje podawaj w formacie KOD=WAGA, np. USD=30."
            )

        currency, raw_weight = token.split("=", maxsplit=1)
        normalized_currency = currency.strip().upper()

        if normalized_currency in allocations:
            raise argparse.ArgumentTypeError(
                f"Waluta {normalized_currency} została podana więcej niż raz."
            )

        try:
            allocations[normalized_currency] = float(raw_weight)
        except ValueError as exc:
            raise argparse.ArgumentTypeError(
                f"Nieprawidłowa waga dla {currency}: {raw_weight}"
            ) from exc

    if len(allocations) != 3:
        raise argparse.ArgumentTypeError(
            "Podaj dokładnie 3 różne waluty w parametrze --allocations."
        )

    return allocations


def parse_pipeline_parameters(description: str, args: Sequence[str] | None = None) -> PipelineParameters:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--amount",
        type=float,
        default=DEFAULT_INVESTMENT_AMOUNT_PLN,
        help="Kwota inwestycji w PLN.",
    )
    parser.add_argument(
        "--start-date",
        type=_parse_iso_date,
        default=DEFAULT_START_DATE,
        help="Data zakupu walut w formacie YYYY-MM-DD.",
    )
    parser.add_argument(
        "--holding-period-days",
        type=int,
        default=DEFAULT_HOLDING_PERIOD_DAYS,
        help="Liczba dni kalendarzowych, przez które portfel jest utrzymywany.",
    )
    parser.add_argument(
        "--allocations",
        nargs="+",
        default=[
            f"{currency}={weight * 100:.0f}"
            for currency, weight in DEFAULT_ALLOCATION.items()
        ],
        help="Trzy udziały walut w formacie KOD=WAGA, np. USD=30 EUR=40 HUF=30.",
    )

    parsed = parser.parse_args(args=args)
    allocations = _parse_allocations(parsed.allocations)

    return build_pipeline_parameters(
        investment_amount_pln=parsed.amount,
        start_date=parsed.start_date,
        holding_period_days=parsed.holding_period_days,
        allocations=allocations,
        weights_are_percent=True,
    )
