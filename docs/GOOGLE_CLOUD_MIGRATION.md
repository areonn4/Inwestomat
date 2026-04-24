# Migracja do Google Cloud

## 1. Cel dokumentu

Ten dokument opisuje, w jaki sposób obecne rozwiązanie może zostać przeniesione z lokalnego środowiska opartego na SQLite i plikach lokalnych do środowiska Google Cloud bez przebudowy logiki biznesowej.

Najważniejsze założenie architektoniczne projektu jest następujące:

- logika transformacji danych jest oddzielona od warstwy przechowywania,
- logika biznesowa jest wykonywana w `pandas`,
- zmiany migracyjne dotyczą przede wszystkim adapterów wejścia i wyjścia danych.

Dzięki temu przejście do Google Cloud nie wymaga przepisywania całego pipeline'u.

## 2. Stan obecny

Aktualna architektura lokalna:

- `extract_service.py` zapisuje dane źródłowe do `SQLite`,
- `transform_service.py` czyta dane z `SQLite` do `pandas.DataFrame`,
- `load_service.py` zapisuje wynik do lokalnego `Parquet` i `JSON`,
- `app.py` odczytuje gotowe artefakty i prezentuje wynik.

## 3. Elementy już gotowe do migracji

Projekt już teraz ma cechy, które ułatwiają migrację do Google Cloud:

- warstwy `extract`, `transform` i `load` są od siebie odseparowane,
- logika obliczeniowa nie jest wymieszana z logiką storage,
- wynik końcowy jest zapisywany do `Parquet`,
- transformacje są wykonywane w `pandas`,
- konfiguracja techniczna jest scentralizowana w `src/config.py`.

## 4. Rola `pandas` w migracji

Biblioteka `pandas` jest już wykorzystywana w projekcie jako centralny silnik transformacji.

Najważniejsze miejsca użycia:

- [src/transform_service.py](../src/transform_service.py)
  - `pd.read_sql_query(...)`
  - `pivot(...)`
  - `reindex(...)`
  - `ffill(...)`
  - wektorowe liczenie portfela
- [src/load_service.py](../src/load_service.py)
  - zapis `DataFrame` do `Parquet`
- [app.py](../app.py)
  - przygotowanie danych do warstwy prezentacyjnej

To jest istotne z perspektywy migracji, ponieważ `pandas`:

- dobrze współpracuje z relacyjnymi bazami danych,
- dobrze współpracuje z plikami analitycznymi,
- jest standardowym narzędziem w skryptach ETL i migracjach danych,
- pozwala zachować czytelność logiki transformacji podczas zmiany warstwy storage.

## 5. Docelowy model migracji

Najbardziej naturalna ścieżka migracji wygląda następująco:

### 5.1 Warstwa raw / staging

Obecnie:

- lokalna baza `SQLite`

Możliwe odpowiedniki w Google Cloud:

- `Cloud SQL` — jeśli staging ma pozostać relacyjny,
- `Google Cloud Storage` — jeśli staging ma być plikowy.

### 5.2 Warstwa transform

Obecnie:

- odczyt danych z SQLite do `pandas`

Możliwe odpowiedniki w Google Cloud:

- odczyt z `Cloud SQL` do `pandas`,
- odczyt z plików w `GCS` do `pandas`.

### 5.3 Warstwa wynikowa

Obecnie:

- lokalny `Parquet` i `JSON`

Możliwe odpowiedniki w Google Cloud:

- zapis `Parquet` do `Google Cloud Storage`,
- załadowanie danych do `BigQuery`,
- zapis metadanych do osobnej tabeli lub pliku w `GCS`.

## 6. Zakres zmian w kodzie

Migracja nie wymagałaby przepisywania całego projektu. Najważniejsze zmiany dotyczyłyby poniższych plików.

### 6.1 `src/config.py`

Do dodania:

- `GCP_PROJECT_ID`
- `GCP_BUCKET_NAME`
- `BIGQUERY_DATASET`
- `BIGQUERY_TABLE`
- `CLOUD_SQL_CONNECTION_NAME`
- opcjonalnie flaga trybu pracy, np. `STORAGE_BACKEND=local|gcp`

### 6.2 `src/extract_service.py`

Aktualnie:

- zapis do SQLite przez `sqlite3.connect(...)`

Możliwe zmiany:

- zapis do `Cloud SQL`,
- albo zapis surowych rekordów do plików i upload do `GCS`.

To jest miejsce, w którym należałoby podmienić adapter zapisu danych źródłowych.

### 6.3 `src/transform_service.py`

Aktualnie:

- odczyt przez `pd.read_sql_query(...)` z SQLite

Możliwe zmiany:

- odczyt z `Cloud SQL`,
- albo odczyt z plików pobranych z `GCS`.

Najważniejsze:

- funkcje `build_daily_rate_frame(...)` i `calculate_portfolio(...)` mogą pozostać bez zmian,
- modyfikacji wymaga tylko sposób pobrania danych wejściowych do `DataFrame`.

### 6.4 `src/load_service.py`

Aktualnie:

- zapis do lokalnego `portfolio.parquet`

Możliwe zmiany:

- upload `Parquet` do `Google Cloud Storage`,
- ładowanie danych do `BigQuery`,
- zapis metadanych do `GCS` lub tabeli technicznej.

To jest miejsce, w którym należałoby podmienić adapter wyjściowy.

## 7. Co może pozostać bez zmian

Przy migracji do Google Cloud bez zmian mogłyby pozostać:

- `src/pipeline_models.py`,
- `src/pipeline_cli.py`,
- większość `src/pipeline.py`,
- większość logiki w `src/transform_service.py`,
- dashboard `app.py`.

To oznacza, że migracja dotyczy głównie warstwy storage i transportu danych, a nie samej logiki biznesowej.

## 8. Przykładowe kierunki implementacyjne

### 8.1 Cloud SQL

Scenariusz:

- `extract_service.py` zapisuje dane do `Cloud SQL`,
- `transform_service.py` odczytuje dane przez połączenie SQL,
- `pandas` pozostaje silnikiem transformacji.

### 8.2 GCS + Parquet

Scenariusz:

- dane surowe lub przetworzone są zapisywane jako pliki,
- pliki są przechowywane w `Google Cloud Storage`,
- transformacje nadal wykonywane są w `pandas`.

### 8.3 BigQuery

Scenariusz:

- wynik końcowy ładowany jest do `BigQuery`,
- dashboard lub kolejne procesy mogą czytać dane z warstwy analitycznej w chmurze.

## 9. Wniosek architektoniczny

Projekt został przygotowany w taki sposób, aby:

- lokalna baza SQLite pełniła rolę stagingu,
- `pandas` odpowiadał za transformacje,
- warstwa storage mogła zostać podmieniona bez przepisywania logiki biznesowej.

Z punktu widzenia oceny technicznej oznacza to, że rozwiązanie nie jest jedynie lokalnym skryptem, ale ma strukturę zgodną z podejściem stosowanym przy migracjach danych do środowisk chmurowych, w tym do Google Cloud.
