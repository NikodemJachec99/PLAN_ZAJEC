# Plan Zajec - Mikrus VPS Deploy

Projekt sklada sie z:
- `backend/` - FastAPI (API i logika planu)
- `frontend/` - React + Vite (UI)

Deploy produkcyjny jest przygotowany pod model Mikrusa:
- 1 aplikacja = 1 port
- n8n zostaje na `20225` (nie dotykamy)
- ta aplikacja dziala na `30225`
- publiczne domeny:
  - `https://patryk225-30225.wykr.es`
  - `https://patryk225-30225.mikrus.cloud`

HTTPS jest terminowane przez proxy Mikrusa, kontenery dzialaja po HTTP.

## Architektura kontenerow

`compose.yaml` uruchamia 2 serwisy:
1. `backend` (FastAPI) - port wewnetrzny `8000`
2. `frontend` (nginx + zbudowany Vite) - wystawiony na hosta: `30225:80`

Nginx serwuje SPA i proxyuje `/api/*` do `backend:8000`.

## Pliki deploy

- `compose.yaml`
- `.dockerignore`
- `.env.example`
- `deploy.sh`
- `frontend/Dockerfile` (multi-stage: node -> nginx)
- `frontend/nginx.conf` (SPA fallback + reverse proxy `/api`)

## Szybki deploy na Mikrusie

### 1) Jednorazowa konfiguracja na VPS

```bash
git clone <TWOJ_REPO_URL>
cd PLAN_ZAJEC
cp .env.example .env
chmod +x deploy.sh
```

### 2) Pierwsze uruchomienie

```bash
./deploy.sh
```

Po deployu aplikacja bedzie dostepna pod:
- `https://patryk225-30225.wykr.es`
- `https://patryk225-30225.mikrus.cloud`

### 3) Kolejne aktualizacje

Po kazdym pushu do gita na VPS wystarczy:

```bash
./deploy.sh
```

Skrypt wykona:
1. `git pull --ff-only`
2. `docker compose build --pull`
3. `docker compose up -d --remove-orphans`
4. `docker image prune -f`

Na koncu wypisze URL aplikacji.

## Ustawienia `.env`

Najwazniejsze zmienne:
- `APP_PORT=30225`
- `APP_URL=https://patryk225-30225.wykr.es`
- `ALLOWED_ORIGINS=...` (domeny publiczne + lokalne dev)
- `CACHE_TTL_SECONDS=60`
- `TZ=Europe/Warsaw`
- `VITE_API_BASE_URL=` (puste = same-origin, przez nginx `/api`)

## Przydatne komendy diagnostyczne

```bash
docker compose -f compose.yaml ps
docker compose -f compose.yaml logs -f
docker compose -f compose.yaml logs -f frontend
docker compose -f compose.yaml logs -f backend
```

## Lokalny dev (bez dockera)

Backend:
```bash
cd backend
python -m pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Frontend:
```bash
cd frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```
