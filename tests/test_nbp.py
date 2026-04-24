import requests
from datetime import date

url = "https://api.nbp.pl/api/exchangerates/rates/a/usd/2024-04-06/2024-04-07/?format=json"
resp = requests.get(url)
print(f"Status for weekend 2024-04-06 (Sat) to 2024-04-07 (Sun): {resp.status_code}")
