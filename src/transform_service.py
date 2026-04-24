from __future__ import annotations

import sqlite3
from contextlib import closing

import pandas as pd

from src.config import DB_PATH, logger
from src.pipeline_models import PipelineParameters


def read_rates_from_db(
    parameters: PipelineParameters,
    db_path=DB_PATH,
) -> pd.DataFrame:
    placeholders = ", ".join("?" for _ in parameters.currencies)
    query = f"""
        SELECT date, currency, rate
        FROM exchange_rates
        WHERE date BETWEEN ? AND ?
          AND currency IN ({placeholders})
        ORDER BY date, currency
    """
    query_params = (
        parameters.buffer_start_date.isoformat(),
        parameters.end_date.isoformat(),
        *parameters.currencies,
    )

    logger.info(
        "Odczyt kursów z SQLite dla zakresu %s - %s",
        parameters.buffer_start_date.isoformat(),
        parameters.end_date.isoformat(),
    )

    with closing(sqlite3.connect(db_path)) as connection:
        dataframe = pd.read_sql_query(
            query,
            connection,
            params=query_params,
            parse_dates=["date"],
        )

    return dataframe


def build_daily_rate_frame(
    raw_rates: pd.DataFrame,
    parameters: PipelineParameters,
) -> pd.DataFrame:
    if raw_rates.empty:
        raise ValueError(
            "Baza SQLite nie zawiera danych dla wybranego zakresu. "
            "Najpierw uruchom etap extract albo pełny pipeline."
        )

    pivoted = (
        raw_rates.assign(date=pd.to_datetime(raw_rates["date"]))
        .pivot(index="date", columns="currency", values="rate")
        .sort_index()
    )

    missing_currencies = [
        currency for currency in parameters.currencies if currency not in pivoted.columns
    ]
    if missing_currencies:
        raise ValueError(
            "Brak kursów w bazie SQLite dla walut: "
            f"{', '.join(missing_currencies)}."
        )

    calendar_index = pd.date_range(
        start=parameters.start_date,
        end=parameters.end_date,
        freq="D",
        name="valuation_date",
    )

    combined_index = pivoted.index.union(calendar_index)
    filled_rates = pivoted.reindex(combined_index).sort_index().ffill()
    daily_rates = filled_rates.reindex(calendar_index)[list(parameters.currencies)]

    if daily_rates.isna().any().any():
        missing_currencies = daily_rates.columns[daily_rates.isna().any()].tolist()
        raise ValueError(
            "Nie udało się zbudować pełnej dziennej serii kursów dla: "
            f"{', '.join(missing_currencies)}. "
            "Zmień datę startu albo odśwież dane w SQLite."
        )

    return daily_rates


def calculate_portfolio(
    daily_rates: pd.DataFrame,
    parameters: PipelineParameters,
) -> pd.DataFrame:
    allocation_series = pd.Series(parameters.allocations, dtype="float64")
    purchase_rates = daily_rates.iloc[0][allocation_series.index]
    if (purchase_rates <= 0).any():
        invalid_currencies = purchase_rates[purchase_rates <= 0].index.tolist()
        raise ValueError(
            "Kurs zakupu musi być dodatni dla walut: "
            f"{', '.join(invalid_currencies)}."
        )
    purchased_units = (
        parameters.investment_amount_pln * allocation_series / purchase_rates
    )

    component_values = daily_rates[allocation_series.index].multiply(
        purchased_units,
        axis="columns",
    )
    total_value = component_values.sum(axis=1)

    report = pd.DataFrame(index=daily_rates.index)
    report.index.name = "valuation_date"
    report["day_number"] = range(len(report))
    report["total_value_pln"] = total_value
    report["daily_change_pln"] = report["total_value_pln"].diff().fillna(0.0)
    report["cumulative_change_pln"] = (
        report["total_value_pln"] - parameters.investment_amount_pln
    )
    report["daily_return_pct"] = report["total_value_pln"].pct_change().fillna(0.0)
    report["cumulative_return_pct"] = (
        report["total_value_pln"] / parameters.investment_amount_pln - 1.0
    )

    units_frame = (
        pd.DataFrame([purchased_units], index=[report.index[0]])
        .reindex(report.index, method="ffill")
        .set_axis(purchased_units.index, axis="columns")
    )

    report = report.join(daily_rates.add_suffix("_rate"))
    report = report.join(units_frame.add_suffix("_units"))
    report = report.join(component_values.add_suffix("_value_pln"))

    return report


def build_portfolio_report(
    parameters: PipelineParameters,
    db_path=DB_PATH,
) -> pd.DataFrame:
    raw_rates = read_rates_from_db(parameters=parameters, db_path=db_path)
    daily_rates = build_daily_rate_frame(raw_rates=raw_rates, parameters=parameters)
    report = calculate_portfolio(daily_rates=daily_rates, parameters=parameters)

    logger.info(
        "Transform zakończony. Raport zawiera %s dni kalendarzowych.",
        len(report),
    )
    return report
