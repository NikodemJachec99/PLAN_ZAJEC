# Plan zajęć – III rok Pielęgniarstwo I st. (WNoZ UO)

Plan zajęć, który **sam się aktualizuje**: backend co kilka minut sprawdza stronę
<https://wnoz.uni.opole.pl/plan-pielegniarstwo-i-stopnia-iii-rok-stacjonarne-1/>,
pobiera wszystkie opublikowane tam pliki `.xlsx` (plan zajęć + harmonogram zajęć
praktycznych) i składa je w jeden plan. Otwarta strona w przeglądarce odświeża się
sama i pokazuje komunikat „Plan został zaktualizowany”.

- `backend/` – FastAPI: synchronizacja ze stroną uczelni, parsowanie Excela, API, eksport `.ics`
- `frontend/` – React + Vite + Tailwind: widoki Dzień / **Tydzień (domyślny)** / Miesiąc / Lista,
  wybór grupy zapamiętywany na urządzeniu (localStorage)

## Jak działa automatyczna aktualizacja

1. Co `SYNC_INTERVAL_SECONDS` (domyślnie 300 s) backend pobiera stronę planu i wyszukuje
   wszystkie linki do plików Excel (zwykłe linki, bloki „Plik” WordPressa, podglądy Office Online).
2. Każdy plik jest pobierany warunkowo (ETag / Last-Modified) i porównywany po sumie SHA-256 –
   wykrywana jest zarówno podmiana linku na nowy plik, jak i podmiana pliku pod tym samym adresem.
3. Rodzaj pliku (plan zajęć czy harmonogram praktyk) rozpoznawany jest **po zawartości**, nie po nazwie.
   Wszystkie rozpoznane pliki tworzą razem jeden plan. Niezwiązane arkusze są pomijane.
4. Przełączenie na nową wersję jest atomowe. Poprzedni plan nigdy nie znika przez błąd:
   - strona uczelni nie odpowiada / nie ma na niej plików → zostaje ostatni plan,
   - nowy plik nie daje się odczytać → zostaje poprzednia wersja tego pliku (z ostrzeżeniem),
   - jeden z plików zniknie ze strony → jego ostatnia wersja jest pokazywana jeszcze przez 12 h.
5. Frontend co minutę (i przy powrocie do karty) pyta `/api/v1/status`; gdy wersja planu się
   zmieni, pobiera nowy plan bez przeładowania strony. Ostatni plan jest też trzymany w
   przeglądarce, więc strona otwiera się natychmiast, nawet bez internetu.

Stan synchronizacji (pliki, sumy kontrolne, ostatnie sprawdzenie, błędy) zapisywany jest w
`backend/data/sources/manifest.json`, więc przetrwa restart. Do czasu pierwszego udanego
pobrania używane są pliki z `backend/data/seed/`.

## Co robi parser (żeby plan nic nie gubił)

- **Plan zajęć** – kolumny znajdowane po nagłówkach (data, od, do, przedmiot, rodzaj, prowadzący,
  sala, grupa, uwagi…), więc przestawienie kolumn niczego nie psuje. Kolejne bloki tych samych zajęć
  są łączone w jeden kafelek, ale każdy blok jest zachowany (`parts`). Przekreślony przedmiot =
  zajęcia odwołane. Wiersze, których nie da się umieścić w planie, są wypisywane jako ostrzeżenia.
- **Harmonogram zajęć praktycznych** – komórki scalone na podgrupy „a” i „b” trafiają do obu
  podgrup; rok dat wyznaczany z roku akademickiego i sprawdzany z dniami tygodnia z nagłówka;
  wpis dopasowywany do legendy po kodzie, kolorze komórki i inicjałach prowadzącego
  (`PZ`, `JSz`, `ES-C`…); godziny z komórki, z legendy (np. Soteria 8:45–20:00) albo
  z podkreślenia (zwykłe 7:00–14:30, podwójne 7:00–18:15). Nierozpoznany wpis nie znika –
  jest pokazywany jako „Zajęcia praktyczne” z oryginalną treścią komórki.

Parser jest sprawdzany testami na aktualnych plikach III roku (zgodność 430/430 wpisów
z danymi z projektu graficznego) oraz na plikach II roku z poprzedniego semestru.

## API

| Endpoint | Opis |
|---|---|
| `GET /api/v1/plan` | cały plan (wydarzenia, przedmioty, grupy, źródła); ETag + gzip |
| `GET /api/v1/status` | wersja planu i stan synchronizacji (do odpytywania co minutę) |
| `POST /api/v1/sync` | poproś o natychmiastowe sprawdzenie strony uczelni (limit: raz na 30 s) |
| `GET /api/v1/calendar.ics?group=1a&lek=A&cw-a=I` | kalendarz dla wybranych grup; dodany jako subskrypcja (przycisk „Subskrybuj”) sam się aktualizuje |
| `POST /api/v1/admin/upload` | awaryjne ręczne wgranie pliku (nagłówek `x-settings-password`); działa do czasu, aż uczelnia opublikuje nowy plik tego rodzaju |
| `DELETE /api/v1/admin/manual` | usunięcie ręcznie wgranych plików |
| `GET /api/v1/health` | healthcheck |

## Konfiguracja (`.env`)

| Zmienna | Domyślnie | Opis |
|---|---|---|
| `SOURCE_PAGE_URL` | strona III roku na wnoz.uni.opole.pl | skąd pobierać pliki |
| `SYNC_INTERVAL_SECONDS` | `300` | jak często sprawdzać stronę (min. 30) |
| `SYNC_MISSING_GRACE_HOURS` | `12` | jak długo pokazywać plik, który zniknął ze strony |
| `SETTINGS_PASSWORD` | puste | hasło do ręcznego wgrywania; puste = wyłączone |
| `SYNC_ENABLED` | `1` | `0` wyłącza synchronizację (np. testy) |
| `APP_PORT`, `APP_URL`, `ALLOWED_ORIGINS`, `TZ`, `VITE_API_BASE_URL` | | jak wcześniej |

## Deploy (Mikrus VPS)

Bez zmian: `compose.yaml` uruchamia `backend` (FastAPI, port wewnętrzny 8000) i `frontend`
(nginx, port `APP_PORT`, proxy `/api` → backend). Katalog `./backend/data` jest montowany do
kontenera, więc pobrane pliki i stan synchronizacji są trwałe.

```bash
cp .env.example .env   # pierwszy raz
./deploy.sh            # git pull + docker compose build + up
```

Kontener backendu musi mieć dostęp do internetu (wychodzący HTTPS do `wnoz.uni.opole.pl`).
Na nowy semestr / rok wystarczy zmienić `SOURCE_PAGE_URL` (jeśli uczelnia zmieni adres strony).

Diagnostyka:

```bash
docker compose logs -f backend          # wpisy "plan.sync" pokazują każdą aktualizację
curl -s localhost:30225/api/v1/status   # ostatnie sprawdzenie, błędy, pliki
```

## Lokalny dev

```bash
# backend
cd backend
python -m pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8000
python -m pytest -q

# frontend (Vite przekierowuje /api na :8000)
cd frontend
npm install
npm run dev
```
