# Plan Zajec - React + FastAPI

Nowa wersja aplikacji jest podzielona na:

- `backend/` - FastAPI API zasilane plikami Excel
- `frontend/` - React + Vite + TypeScript + Tailwind

## Lokalny start

### 1) Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

API: `http://localhost:8000`
Dokumentacja: `http://localhost:8000/docs`

### 2) Frontend

```bash
cd frontend
npm install
npm run dev
```

UI: `http://localhost:5173`

Opcjonalnie utworz plik `frontend/.env`:

```env
VITE_API_BASE_URL=http://localhost:8000
```

## API kontrakt

- `GET /api/v1/health`
- `GET /api/v1/meta`
- `GET /api/v1/schedule/day?date=YYYY-MM-DD&subject=...`
- `GET /api/v1/schedule/week?anchor_date=YYYY-MM-DD&subject=...`

Wspierane filtry (powtarzalne query params):

- `subject`
- `instructor`
- `room`
- `group`
- `oddzial`
- `type`
- `only_magdalenka=true|false`

## Dane

Pliki wejsciowe znajduja sie w `backend/data/`:

- `plan_zajec.xlsx` (wymagany)
- `praktyki_tidy (1).xlsx` lub `praktyki_tidy.xlsx` (opcjonalny)

Backend odswieza cache co 60 sekund i dodatkowo reaguje na zmiane plikow.

## Testy backendu

```bash
cd backend
pytest
```

## Deploy

### Railway (backend)

- Projekt uzywa `backend/Dockerfile`
- Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Env vars:
  - `DATA_DIR=/app/data`
  - `CACHE_TTL_SECONDS=60`
  - `ALLOWED_ORIGINS=https://<twoj-frontend>.vercel.app,http://localhost:5173`
  - `TZ=Europe/Warsaw`

### Vercel (frontend)

- Root directory: `frontend`
- Env var:
  - `VITE_API_BASE_URL=https://<twoj-backend>.up.railway.app`

## Legacy

Stary prototyp Streamlit pozostaje w `plan_app.py`.
