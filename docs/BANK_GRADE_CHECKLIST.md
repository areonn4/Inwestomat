# Bank-Grade Checklist

Projekt został przygotowany w stylu korporacyjnego mini-pipeline'u danych, ale nie powinien być opisywany jako rozwiązanie „w 100% bezpieczne”. Poniżej znajduje się rozdzielenie na:

- elementy już wdrożone w repozytorium,
- elementy, które należałoby dołożyć przed wdrożeniem produkcyjnym.

## Już wdrożone

- parametry wejściowe są walidowane: kwota, data startu, długość inwestycji, dokładnie 3 różne waluty i suma wag = 100%,
- do bazy SQLite używane są zapytania parametryzowane,
- baza ma idempotentny `upsert` po `(date, currency)`,
- pipeline ma lokalną warstwę `landing zone` w SQLite,
- pipeline próbuje użyć danych lokalnych, jeśli API NBP tymczasowo nie działa,
- wynik analityczny jest zapisany do Parquet, a przebieg do metadanych JSON,
- dashboard nie zakłada błędnie, że dane zawsze są poprawne; pokazuje kontrolowane komunikaty błędów,
- projekt ma testy automatyczne dla walidacji, weekendowego `forward-fill`, zapisu artefaktów i fallbacku cache.

## Co należałoby dołożyć przed wdrożeniem produkcyjnym

- pełny zestaw testów integracyjnych i regresyjnych w CI/CD,
- skanowanie zależności pod kątem CVE oraz pinning z hashami,
- secrets management zamiast lokalnej konfiguracji w kodzie,
- szyfrowanie danych w spoczynku i politykę retencji danych,
- monitoring, alerting i raportowanie nieudanych przebiegów,
- centralne logowanie z korelacją zdarzeń i audytem,
- backup bazy danych i testy odtwarzania,
- kontrolę uprawnień do uruchamiania pipeline oraz dostępu do artefaktów,
- formalny przegląd bezpieczeństwa i model zagrożeń,
- środowiska `dev / test / prod` oraz release management.

## Wniosek

Repozytorium pokazuje poprawny kierunek architektoniczny, dobre praktyki przetwarzania danych i świadome przygotowanie pod środowisko regulowane. Nie jest to gotowy system produkcyjny banku, ale jest to rozwiązanie zaprojektowane tak, aby można je było dalej utwardzać i migrować do środowiska enterprise.
