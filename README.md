# Inwestomat
[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://inwestomat.streamlit.app/)
Link do aplikacji: https://inwestomat.streamlit.app/
Projekt realizuje zadanie kwalifikacyjne jako mały, ale profesjonalny pipeline danych do analizy portfela walutowego opartego na kursach NBP.

Rozwiązanie:

- pobiera dane z API NBP,
- zapisuje surowe dane do lokalnej bazy SQLite,
- wykonuje transformacje w `pandas`,
- zapisuje wynik do formatu `Parquet`,
- prezentuje rezultat w dashboardzie Streamlit.

Projekt został przygotowany tak, aby pokazywał nie tylko znajomość logiki biznesowej i podstaw rynku, ale również umiejętność budowania skryptowego pipeline'u danych gotowego do dalszej migracji do Google Cloud.

## Architektura rozwiązania

Repozytorium jest podzielone na wyraźne warstwy:

- [src/01_extract_api.py](src/01_extract_api.py) — etap pobrania danych do SQLite
- [src/02_transform.py](src/02_transform.py) — etap transformacji i kalkulacji portfela
- [src/03_load_cloud.py](src/03_load_cloud.py) — etap zapisu do Parquet
- [run_pipeline.py](run_pipeline.py) — pełny orchestrator `extract -> transform -> load`
- [start.py](start.py) — jeden plik startowy uruchamiający ETL oraz dashboard
- [app.py](app.py) — interaktywny dashboard
- `data/raw/rates.db` — lokalna warstwa `landing zone`
- `data/processed/portfolio.parquet` — gotowy model analityczny
- `data/processed/portfolio_metadata.json` — metadane przebiegu

## Wymagania

```bash
pip install -r requirements.txt
```

## Testy

```bash
python -m unittest discover -s tests -v
```

## Uruchomienie

### Pełny pipeline

```bash
python run_pipeline.py --start-date 2026-03-25 --amount 1000 --allocations USD=30 EUR=40 HUF=30
```

### Jeden plik startowy do całego projektu

```bash
python start.py --start-date 2026-03-25 --amount 1000 --allocations USD=30 EUR=40 HUF=30
```

Powyższe polecenie:

- uruchamia pełny pipeline `extract -> transform -> load`,
- zapisuje dane do SQLite, Parquet i JSON,
- następnie uruchamia dashboard Streamlit.

### Uruchomienie samego dashboardu

```bash
python start.py --skip-pipeline
```

### Etapy osobno

```bash
python src/01_extract_api.py --start-date 2026-03-25 --allocations USD=30 EUR=40 HUF=30
python src/02_transform.py --start-date 2026-03-25 --amount 1000 --allocations USD=30 EUR=40 HUF=30
python src/03_load_cloud.py --start-date 2026-03-25 --amount 1000 --allocations USD=30 EUR=40 HUF=30
```

## Dashboard

```bash
streamlit run app.py
```

W dashboardzie użytkownik podaje:

- kwotę inwestycji,
- datę startu,
- 3 waluty,
- procentowy podział portfela.

## Założenia biznesowe

- inwestycja trwa `30` dni kalendarzowych, więc raport zawiera `31` punktów od `Day 0` do `Day 30`,
- waluty są kupowane tylko raz, w dacie startu,
- dla weekendów i świąt stosowany jest ostatni dostępny średni kurs NBP,
- przy błędzie API pipeline próbuje użyć danych już zapisanych w SQLite.

## Pandas w projekcie

Tak, biblioteka `pandas` jest wykorzystywana w projekcie jako główny silnik transformacji danych.

Najważniejsze zastosowania:

- odczyt danych z SQL do `DataFrame`,
- pivot danych walutowych do układu dziennego,
- budowa pełnego kalendarza wycen,
- uzupełnianie braków kursowych metodą `forward-fill`,
- wektorowe liczenie portfela i stóp zwrotu,
- zapis danych przetworzonych do `Parquet`,
- przygotowanie danych do warstwy prezentacyjnej w dashboardzie.

To jest istotne w kontekście migracji do Google Cloud, ponieważ `pandas` jest standardowym narzędziem w skryptach migracyjnych oraz procesach ETL.

## Bezpieczeństwo i jakość

- SQLite używa zapytań parametryzowanych,
- baza ma idempotentny `upsert` po `(date, currency)`,
- pipeline zapisuje metadane przebiegu do JSON,
- wynik końcowy jest zapisany w formacie `Parquet`,
- projekt ma automatyczne testy jednostkowe dla walidacji, transformacji, fallbacku i zapisu artefaktów.

## Dokumentacja

- [docs/PROJECT_DOCUMENTATION.md](docs/PROJECT_DOCUMENTATION.md) — kompletna dokumentacja architektury, przepływu danych i odpowiedzialności komponentów
- [docs/GOOGLE_CLOUD_MIGRATION.md](docs/GOOGLE_CLOUD_MIGRATION.md) — opis ścieżki migracji z lokalnego rozwiązania do Google Cloud
- [docs/BANK_GRADE_CHECKLIST.md](docs/BANK_GRADE_CHECKLIST.md) — checklista jakościowa i bezpieczeństwa dla rozwiązania w stylu korporacyjnym
