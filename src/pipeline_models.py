from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from math import isfinite
from typing import Mapping

from src.config import API_LOOKBACK_BUFFER_DAYS, SUPPORTED_CURRENCIES


class ConfigurationError(ValueError):
    """Raised when the pipeline parameters are invalid."""


@dataclass(frozen=True, slots=True)
class PipelineParameters:
    investment_amount_pln: float
    start_date: date
    holding_period_days: int
    allocations: dict[str, float]

    def __post_init__(self) -> None:
        if not isinstance(self.start_date, date):
            raise ConfigurationError("Data startu musi być poprawną datą.")

        normalized_allocations = {
            currency.upper(): float(weight)
            for currency, weight in self.allocations.items()
        }

        if not isfinite(self.investment_amount_pln) or self.investment_amount_pln <= 0:
            raise ConfigurationError("Kwota inwestycji musi być większa od zera.")

        if self.holding_period_days <= 0:
            raise ConfigurationError("Liczba dni inwestycji musi być dodatnia.")

        if len(normalized_allocations) != 3:
            raise ConfigurationError("Zadanie wymaga dokładnie 3 różnych walut.")

        unsupported_currencies = sorted(
            currency
            for currency in normalized_allocations
            if currency not in SUPPORTED_CURRENCIES
        )
        if unsupported_currencies:
            raise ConfigurationError(
                "Nieobsługiwane waluty: "
                f"{', '.join(unsupported_currencies)}. "
                f"Dostępne: {', '.join(SUPPORTED_CURRENCIES)}."
            )

        if any(
            not isfinite(weight) or weight <= 0
            for weight in normalized_allocations.values()
        ):
            raise ConfigurationError("Każda waga alokacji musi być dodatnia.")

        total_weight = sum(normalized_allocations.values())
        if abs(total_weight - 1.0) > 1e-6:
            raise ConfigurationError("Suma udziałów walut musi wynosić dokładnie 100%.")

        if self.end_date > date.today():
            raise ConfigurationError(
                "Data końcowa inwestycji nie może wypadać w przyszłości."
            )

        object.__setattr__(self, "allocations", normalized_allocations)

    @property
    def currencies(self) -> tuple[str, ...]:
        return tuple(self.allocations.keys())

    @property
    def end_date(self) -> date:
        return self.start_date + timedelta(days=self.holding_period_days)

    @property
    def buffer_start_date(self) -> date:
        return self.start_date - timedelta(days=API_LOOKBACK_BUFFER_DAYS)

    @property
    def allocation_percentages(self) -> dict[str, float]:
        return {
            currency: round(weight * 100.0, 2)
            for currency, weight in self.allocations.items()
        }

    def to_metadata(self) -> dict[str, object]:
        return {
            "investment_amount_pln": round(self.investment_amount_pln, 2),
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "holding_period_days": self.holding_period_days,
            "allocations": self.allocation_percentages,
        }


def build_pipeline_parameters(
    *,
    investment_amount_pln: float,
    start_date: date,
    holding_period_days: int,
    allocations: Mapping[str, float],
    weights_are_percent: bool = False,
) -> PipelineParameters:
    normalized_allocations = {
        currency.upper(): float(weight) / (100.0 if weights_are_percent else 1.0)
        for currency, weight in allocations.items()
    }

    return PipelineParameters(
        investment_amount_pln=float(investment_amount_pln),
        start_date=start_date,
        holding_period_days=int(holding_period_days),
        allocations=normalized_allocations,
    )
