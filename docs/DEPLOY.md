# Deploying AIROD

Two services, one repo:

| Service | Platform | Root directory | What it is |
|---|---|---|---|
| Dashboard | **Vercel** | `web` | Next.js UI |
| Backend | **Railway** | repo root | FastAPI wrapper around the Python core |

The dashboard works on its own in **mock mode**. Wiring the backend adds
real-model runs.

## 1. Vercel (dashboard)

The repo root has a `requirements.txt`, so Vercel's auto-detect will guess
"Python" and fail with *"No python entrypoint found."* Fix it in one setting:

1. Vercel → your project → **Settings → Build & Deployment → Root Directory**.
2. Set it to **`web`** and save.
3. Redeploy. Vercel now builds the Next.js app.

With no other config, the UI runs the **mock** debate engine — instant, no key.

## 2. Railway (backend)

Railway builds the repo root. The included `Procfile` and `railway.json` tell it
to start the FastAPI app with uvicorn and health-check `/health`.

1. Create a Railway service from this repo (root directory = repo root).
2. **Variables** → add `ANTHROPIC_API_KEY` (required for live runs).
3. **Settings → Networking → Generate Domain** so the service has a public URL.
4. (Recommended) **Add a Volume** mounted at `/data`, then set
   `AIROD_DB=/data/airod_memory.db` so project memory persists across deploys.

Verify: open `https://<your-railway-domain>/health` → `{"ok": true, ...}`.

## 3. Connect them

In Vercel → **Settings → Environment Variables**, add:

```
AIROD_API_URL = https://<your-railway-domain>
```

Redeploy the Vercel app. The dashboard's `/api/run` route now proxies to Railway
for real model runs; if the backend is ever unreachable it falls back to the mock
so the UI never dead-ends.

## Environment variables reference

| Var | Where | Purpose |
|---|---|---|
| `AIROD_API_URL` | Vercel | Railway backend URL; unset = mock mode |
| `ANTHROPIC_API_KEY` | Railway | Enables live model runs |
| `AIROD_DB` | Railway | Memory DB path (use a volume for persistence) |
| `AIROD_AGENTS` | Railway | Path to agents YAML (default `config/agents.yaml`) |
