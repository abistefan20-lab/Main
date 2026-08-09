# Analiza razelor comerciale Staer

Fluxul automat de regenerare folosește numai cod și date text. Livrabilele
binare se reconstruiesc fără o cheie Google și fără apeluri Google API.

## Citește rezultatele direct în GitHub

Deschide [`output/REZUMAT_REZULTATE.md`](output/REZUMAT_REZULTATE.md). Raportul
include concluziile, indicatorii celor trei magazine și distribuțiile pe
distanțe și poate fi citit fără descărcare.

## Generează și descarcă livrabilele

1. Deschide fila **Actions** a repository-ului.
2. Selectează workflow-ul **„Generează livrabilele Staer”**.
3. Apasă **Run workflow**, apoi confirmă cu butonul verde **Run workflow**.
4. După terminarea execuției, deschide execuția finalizată.
5. În secțiunea **Artifacts**, descarcă **`livrabile-staer`**.

Arhiva artifactului conține:

- `raza_comerciala_staer.xlsx` — raportul Excel;
- `harta_raze_staer.html` — harta interactivă;
- `rezumat_raze_staer.pdf` — rezumatul PDF.

Fișierele sunt generate de
[`scripts/analiza_raze_staer.py`](scripts/analiza_raze_staer.py) exclusiv din:

- `data/sursa_analiza_staer.csv`;
- `cache/geocoding_cache.jsonl`;
- `cache/routes_cache.jsonl`;
- `cache/geocoding_run_summary.json`.

Integritatea acestor intrări este verificată înainte de analiză folosind
checksumurile SHA-256 din [`manifest_date_staer.json`](manifest_date_staer.json).

## Regenerare locală

Este necesar Python 3.12 sau o versiune compatibilă:

```bash
python -m pip install -r requirements.txt
python -m pytest -q
python scripts/analiza_raze_staer.py
```

Scriptul nu conține cod de rețea, nu citește chei API și oprește execuția dacă
un fișier de intrare nu mai corespunde manifestului.
