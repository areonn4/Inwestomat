from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from src.config import (
    CURRENCY_COLORS,
    DEFAULT_ALLOCATION,
    DEFAULT_HOLDING_PERIOD_DAYS,
    DEFAULT_INVESTMENT_AMOUNT_PLN,
    DEFAULT_START_DATE,
    PROCESSED_DATA_PATH,
    SUPPORTED_CURRENCIES,
    logger,
)
from src.pipeline import load_existing_analysis, run_pipeline
from src.pipeline_models import ConfigurationError, build_pipeline_parameters


TAB_ICON_PATH = Path(__file__).resolve().parent / "assets" / "favicon-transparent.svg"


st.set_page_config(
    page_title="Analiza Portfela Walutowego",
    page_icon=str(TAB_ICON_PATH),
    layout="wide",
)

st.markdown(
    """
    <style>
    [data-testid="stMainMenuPopover"] [data-testid="stMainMenuItem-theme-System"],
    [data-testid="stMainMenuPopover"] [data-testid="stMainMenuItem-print"],
    [data-testid="stMainMenuPopover"] [data-testid="stMainMenuItem-recordScreencast"],
    [data-testid="stMainMenuPopover"] [role="separator"],
    [data-testid="stMainMenuPopover"] div:has(> button[aria-label="Copy version to clipboard"]) {
        display: none !important;
    }
    
    /* Ukrywa ikonę "Download as CSV" pojawiającą się po najechaniu na tabelę */
    [data-testid="stElementToolbar"] button[title="Download as CSV"],
    [data-testid="stElementToolbar"] button[aria-label="Download as CSV"] {
        display: none !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def format_pln(value: float) -> str:
    return f"{value:,.2f} PLN"


def format_pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def get_portfolio_value_domain(dataframe: pd.DataFrame) -> list[float]:
    min_value = float(dataframe["total_value_pln"].min())
    max_value = float(dataframe["total_value_pln"].max())
    spread = max_value - min_value
    baseline = max(abs(min_value), abs(max_value), 1.0)
    padding = max(spread * 0.25, baseline * 0.0015, 0.5)

    if spread == 0:
        padding = max(baseline * 0.002, 1.0)

    return [min_value - padding, max_value + padding]


def build_allocation_chart(dataframe: pd.DataFrame, currencies: list[str]) -> alt.Chart:
    color_range = [CURRENCY_COLORS.get(currency, "#64748b") for currency in currencies]

    return (
        alt.Chart(dataframe)
        .mark_bar(size=34)
        .encode(
            y=alt.Y("snapshot:N", title=None, sort=["Start", "Koniec"]),
            x=alt.X(
                "share_pct:Q",
                title="Udział w portfelu",
                axis=alt.Axis(format="%"),
                stack="normalize",
            ),
            color=alt.Color(
                "currency:N",
                title="Waluta",
                scale=alt.Scale(domain=currencies, range=color_range),
            ),
            tooltip=[
                alt.Tooltip("snapshot:N", title="Moment"),
                alt.Tooltip("currency:N", title="Waluta"),
                alt.Tooltip("value_pln:Q", title="Wartość", format=",.2f"),
                alt.Tooltip("share_pct:Q", title="Udział", format=".2%"),
            ],
        )
        .properties(height=160)
    )


def build_value_history_chart(dataframe: pd.DataFrame) -> alt.Chart:
    value_domain = get_portfolio_value_domain(dataframe)

    return (
        alt.Chart(dataframe)
        .mark_line(point=True, strokeWidth=3)
        .encode(
            x=alt.X("valuation_date:T", title="Data"),
            y=alt.Y(
                "total_value_pln:Q",
                title="Wartość portfela [PLN]",
                scale=alt.Scale(domain=value_domain, zero=False, nice=False),
                axis=alt.Axis(format=",.2f"),
            ),
            tooltip=[
                alt.Tooltip("valuation_date:T", title="Data"),
                alt.Tooltip("day_number:Q", title="Dzień"),
                alt.Tooltip("total_value_pln:Q", title="Wartość", format=",.2f"),
                alt.Tooltip(
                    "cumulative_change_pln:Q",
                    title="Zmiana od startu",
                    format=",.2f",
                ),
            ],
        )
        .properties(height=320)
    )


def build_daily_change_chart(dataframe: pd.DataFrame) -> alt.Chart:
    return (
        alt.Chart(dataframe)
        .mark_bar()
        .encode(
            x=alt.X("valuation_date:T", title="Data"),
            y=alt.Y("daily_change_pln:Q", title="Zmiana dzienna [PLN]"),
            color=alt.condition(
                alt.datum.daily_change_pln >= 0,
                alt.value("#059669"),
                alt.value("#dc2626"),
            ),
            tooltip=[
                alt.Tooltip("valuation_date:T", title="Data"),
                alt.Tooltip("daily_change_pln:Q", title="Zmiana", format=",.2f"),
                alt.Tooltip("daily_return_pct:Q", title="Stopa zwrotu", format=".2%"),
            ],
        )
        .properties(height=260)
    )


def prepare_chart_frames(dataframe: pd.DataFrame, currencies: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    reset = dataframe.reset_index()
    valuation_date_column = dataframe.index.name or "index"
    history_frame = reset.rename(columns={valuation_date_column: "valuation_date"})

    start_values = dataframe.iloc[0][[f"{currency}_value_pln" for currency in currencies]]
    end_values = dataframe.iloc[-1][[f"{currency}_value_pln" for currency in currencies]]

    allocation_frame = pd.concat(
        {
            "Start": start_values,
            "Koniec": end_values,
        },
        names=["snapshot"],
    ).rename("value_pln").reset_index()

    allocation_frame = allocation_frame.rename(columns={"level_1": "value_column"})
    allocation_frame["currency"] = allocation_frame["value_column"].str.replace(
        "_value_pln",
        "",
        regex=False,
    )
    allocation_frame["share_pct"] = allocation_frame.groupby("snapshot")["value_pln"].transform(
        lambda values: values / values.sum()
    )

    return history_frame, allocation_frame


def render_sidebar() -> tuple[bool, dict[str, object]]:
    st.sidebar.header("Parametry analizy")

    amount = st.sidebar.number_input(
        "Kwota inwestycji [PLN]",
        min_value=100.0,
        value=DEFAULT_INVESTMENT_AMOUNT_PLN,
        step=100.0,
    )

    holding_period_days = int(
        st.sidebar.number_input(
            "Liczba dni inwestycji",
            min_value=1,
            max_value=365,
            value=DEFAULT_HOLDING_PERIOD_DAYS,
            step=1,
        )
    )

    latest_start_date = date.today() - timedelta(days=holding_period_days)
    default_start_date = min(DEFAULT_START_DATE, latest_start_date)

    start_date = st.sidebar.date_input(
        "Data zakupu walut",
        value=default_start_date,
        max_value=latest_start_date,
    )

    st.sidebar.caption(
        f"Koniec inwestycji wypadnie: {(start_date + timedelta(days=holding_period_days)).isoformat()}"
    )

    default_currencies = list(DEFAULT_ALLOCATION.keys())
    default_weights = [int(weight * 100) for weight in DEFAULT_ALLOCATION.values()]

    selected_currencies: list[str] = []
    weights: list[float] = []

    for idx in range(3):
        st.sidebar.markdown(f"**Waluta {idx + 1}**")
        default_currency = default_currencies[idx]
        selected_currency = st.sidebar.selectbox(
            f"Kod waluty {idx + 1}",
            options=SUPPORTED_CURRENCIES,
            index=SUPPORTED_CURRENCIES.index(default_currency),
            key=f"currency_{idx}",
        )
        weight = st.sidebar.number_input(
            f"Udział {selected_currency} [%]",
            min_value=1.0,
            max_value=100.0,
            value=float(default_weights[idx]),
            step=1.0,
            key=f"weight_{idx}",
        )
        selected_currencies.append(selected_currency)
        weights.append(weight)

    total_weight = sum(weights)
    st.sidebar.metric("Suma udziałów", f"{total_weight:.0f}%")
    st.sidebar.caption(
        "Dla weekendów i świąt używany jest ostatni dostępny średni kurs NBP."
    )

    return st.sidebar.button("Uruchom analizę", use_container_width=True), {
        "amount": amount,
        "holding_period_days": holding_period_days,
        "start_date": start_date,
        "currencies": selected_currencies,
        "weights": weights,
    }


def render_dashboard(result) -> None:
    dataframe = result.data.copy()
    metadata = result.metadata
    currencies = list(metadata.get("allocations", {}).keys())
    if not currencies:
        currencies = [
            column.replace("_value_pln", "")
            for column in dataframe.columns
            if column.endswith("_value_pln")
        ]

    history_frame, allocation_frame = prepare_chart_frames(dataframe, currencies)

    st.title("Automatyzacja analizy portfela walutowego")
    st.caption(
        f"Zakres inwestycji: {metadata.get('start_date', '-')} - {metadata.get('end_date', '-')}"
    )

    if metadata.get("refreshed_currencies") or metadata.get("cached_currencies"):
        refreshed = ", ".join(metadata.get("refreshed_currencies", [])) or "-"
        cached = ", ".join(metadata.get("cached_currencies", [])) or "-"
        st.info(
            f"Źródła danych: API odświeżyło {refreshed}. "
            f"Z lokalnej bazy użyto {cached}."
        )

    if metadata.get("pricing_rule"):
        st.caption(str(metadata["pricing_rule"]))

    first_row = dataframe.iloc[0]
    last_row = dataframe.iloc[-1]

    metric_1, metric_2, metric_3, metric_4 = st.columns(4)
    metric_1.metric("Kapitał początkowy", format_pln(float(first_row["total_value_pln"])))
    metric_2.metric(
        "Wartość końcowa",
        format_pln(float(last_row["total_value_pln"])),
        delta=format_pln(float(last_row["cumulative_change_pln"])),
    )
    metric_3.metric(
        "Stopa zwrotu",
        format_pct(float(last_row["cumulative_return_pct"])),
    )
    metric_4.metric(
        "Okres analizy",
        f"{int(metadata.get('holding_period_days', len(dataframe) - 1))} dni",
    )

    left_column, right_column = st.columns((1, 1))

    with left_column:
        st.subheader("Struktura portfela na starcie i na końcu")
        st.altair_chart(
            build_allocation_chart(allocation_frame, currencies),
            use_container_width=True,
        )

    with right_column:
        st.subheader("Parametry i zakupione jednostki")
        parameters_frame = pd.DataFrame(
            {
                "Waluta": currencies,
                "Udział [%]": [
                    metadata.get("allocations", {}).get(currency, 0.0)
                    for currency in currencies
                ],
                "Kurs zakupu": [
                    metadata.get("purchase_rates", {}).get(currency, 0.0)
                    for currency in currencies
                ],
                "Kupione jednostki": [
                    metadata.get("units_purchased", {}).get(currency, 0.0)
                    for currency in currencies
                ],
            }
        )
        st.dataframe(parameters_frame, use_container_width=True, hide_index=True)
        st.download_button(
            label="Pobierz parametry (CSV dla Excela)",
            data=parameters_frame.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig"),
            file_name="parametry_portfela.csv",
            mime="text/csv",
            key="download_params_csv"
        )

    st.subheader("Historia wartości portfela")
    st.altair_chart(build_value_history_chart(history_frame), use_container_width=True)

    st.subheader("Dzienna zmiana względem poprzedniego dnia")
    st.altair_chart(build_daily_change_chart(history_frame), use_container_width=True)

    st.subheader("Szczegóły dzienne")
    details_frame = history_frame.copy()
    details_frame["cumulative_return_pct_display"] = (
        details_frame["cumulative_return_pct"] * 100.0
    )
    daily_columns = [
        "valuation_date",
        "day_number",
        "total_value_pln",
        "daily_change_pln",
        "cumulative_change_pln",
        "cumulative_return_pct_display",
        *[f"{currency}_value_pln" for currency in currencies],
    ]
    display_frame = details_frame[daily_columns].rename(
        columns={
            "valuation_date": "Data",
            "day_number": "Dzień",
            "total_value_pln": "Wartość portfela [PLN]",
            "daily_change_pln": "Zmiana dzienna [PLN]",
            "cumulative_change_pln": "Zmiana od startu [PLN]",
            "cumulative_return_pct_display": "Stopa zwrotu od startu",
            **{
                f"{currency}_value_pln": f"{currency} [PLN]"
                for currency in currencies
            },
        }
    )

    st.dataframe(
        display_frame,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Stopa zwrotu od startu": st.column_config.NumberColumn(format="%.2f%%"),
        },
    )

    st.download_button(
        label="Pobierz szczegóły dzienne (CSV dla Excela)",
        data=display_frame.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig"),
        file_name="historia_portfela.csv",
        mime="text/csv",
        key="download_history_csv"
    )


def main() -> None:
    run_clicked, ui_values = render_sidebar()

    if run_clicked:
        try:
            allocations = dict(zip(ui_values["currencies"], ui_values["weights"], strict=True))
            parameters = build_pipeline_parameters(
                investment_amount_pln=float(ui_values["amount"]),
                start_date=ui_values["start_date"],
                holding_period_days=int(ui_values["holding_period_days"]),
                allocations=allocations,
                weights_are_percent=True,
            )
        except ConfigurationError as exc:
            st.error(str(exc))
        else:
            try:
                with st.spinner("Buduję pipeline, pobieram dane z NBP i przeliczam portfel..."):
                    result = run_pipeline(parameters=parameters, refresh_from_api=True)
            except Exception as exc:
                logger.exception("Pipeline execution failed in Streamlit app.")
                st.error(
                    "Pipeline nie zakończył się powodzeniem. "
                    "Sprawdź parametry wejściowe oraz dostępność danych NBP."
                )
                st.caption(f"Szczegół techniczny: {exc}")
            else:
                st.session_state["analysis_result"] = result
                st.success(
                    f"Pipeline zakończył się sukcesem. Wyniki zapisano do {PROCESSED_DATA_PATH}."
                )

    result = st.session_state.get("analysis_result")

    if result is None:
        try:
            result = load_existing_analysis()
        except Exception as exc:
            logger.exception("Failed to load previously saved analysis.")
            st.warning(
                "Znaleziono zapisane artefakty, ale nie udało się ich bezpiecznie odczytać. "
                "Uruchom analizę ponownie, aby odbudować dane."
            )
            st.caption(f"Szczegół techniczny: {exc}")
            result = None
        else:
            if result is not None:
                st.session_state["analysis_result"] = result

    if result is None:
        st.title("Automatyzacja analizy portfela walutowego")
        st.info(
            "Nie znaleziono jeszcze gotowego pliku Parquet. "
            "Ustaw parametry po lewej stronie i uruchom analizę."
        )
        return

    render_dashboard(result)


if __name__ == "__main__":
    main()
