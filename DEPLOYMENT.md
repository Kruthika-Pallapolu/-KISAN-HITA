# Kisan Hita (కిసాన్ హిత) — Production Deployment & Operations Guide

This guide provides step-by-step procedures to deploy, operate, and maintain the Kisan Hita backend in production cloud environments.

---

## 1. Architecture Overview

Kisan Hita is built on a high-throughput, async Python stack designed for low-latency agricultural advisory:

- **Framework**: FastAPI (ASGI) running on Uvicorn.
- **Persistence**: SQLite database (`kisan_hita.db`) storing user profiles, conversation history, and sequential slot sessions.
- **Reasoning Provider**: Google Gemini 2.5 Flash for natural-language understanding, multi-turn reasoning, and crop foliage visual inspection.
- **Data Providers**:
  - **Market Prices**: Local illustrative references are clearly labeled and are not live official prices.
  - **Crop Advisor**: Verified recommendations are disabled until regional source documents are bundled and traceable.
  - **Crop Health**: Cautious symptom appraisal, root aeration guidelines, and KVK helpline referrals (`1800-180-1551`).
- **Voice Protection**: Zero Gnani live credits consumed during development (`GNANI_LIVE_ENABLED=false`).
- **Browser identity**: Anonymous server-issued session in an HttpOnly cookie; conversation and profile records are isolated by session.

---

## 2. Cloud Deployment Options

### Option A: Docker / Container Platform (Recommended)

The included `Dockerfile` builds a production-hardened container using `python:3.11-slim`, running under a non-root `kisan` user (UID 1000) with a built-in readiness healthcheck.

#### 1. Build the Docker Image
```bash
docker build -t kisan-hita-backend:latest .
```

#### 2. Run the Container Locally or in Cloud VM
```bash
docker run -d \
  --name kisan-backend \
  -p 8000:8000 \
  -v $(pwd)/data:/data \
  -e GEMINI_API_KEY="your-gemini-api-key" \
  -e ALLOWED_ORIGINS="https://your-domain.com" \
  -e COOKIE_SECURE="true" \
  kisan-hita-backend:latest
```

---

### Option B: Google Cloud Run (Serverless Container)

Google Cloud Run is an ideal serverless deployment target for Kisan Hita.

#### 1. Authenticate with Google Cloud
```bash
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
```

#### 2. Build & Push via Google Cloud Artifact Registry
```bash
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/kisan-hita-backend
```

#### 3. Deploy Service to Cloud Run
```bash
gcloud run deploy kisan-hita-backend \
  --image gcr.io/YOUR_PROJECT_ID/kisan-hita-backend \
  --platform managed \
  --region asia-south1 \
  --allow-unauthenticated \
  --set-env-vars GEMINI_API_KEY="your-gemini-key",ALLOWED_ORIGINS="https://your-frontend.vercel.app",GNANI_LIVE_ENABLED="false"
```

> [!NOTE]
> For persistent SQLite storage on Cloud Run, attach a **Cloud Storage Volume (GCS)** or **Cloud SQL instance** via the Google Cloud Run volume mounts feature.

---

### Option C: Platform-as-a-Service (Railway / Render / Fly.io)

Kisan Hita includes a standard `Procfile` for one-click deployment on Git-integrated platforms. Configure the frontend host to reverse-proxy `/api/*` to this backend so the browser cookie remains same-origin. A Vite development proxy is not a production proxy; a separately hosted frontend must configure an equivalent same-origin rewrite.

1. Connect your repository to Railway or Render.
2. Set Environment Variables in the platform dashboard:
   - `GEMINI_API_KEY`: Your Google AI Studio key.
   - `GEMINI_MODEL`: `gemini-2.5-flash`
   - `ALLOWED_ORIGINS`: Explicit frontend origin(s), never `*`.
   - `COOKIE_SECURE`: `true` in HTTPS production.
   - `GNANI_LIVE_ENABLED`: `false`
   - `DATABASE_PATH`: `/data/kisan_hita.db` (attach a persistent volume mounted at `/data`).
3. Deploy command executes automatically:
   ```bash
   uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT
   ```

---

## 3. Database Persistence Strategy

### SQLite Volume Persistence
By default, the application uses SQLite (`DATABASE_PATH=kisan_hita.db`). For single-instance container deployments:
- Mount a persistent host directory to `/data` in the container.
- Set `DATABASE_PATH=/data/kisan_hita.db`.
- The application automatically calls `init_db()` on startup to create tables and indexes if not present.

### PostgreSQL Migration Path
If scaling horizontally across multiple container replicas, migrate SQLite models to PostgreSQL:
1. Replace `sqlite3.connect` in `backend/app/database.py` with `asyncpg` or `psycopg2` / SQLAlchemy session pool.
2. Use standard relational schema: `user_profiles`, `conversations`, `messages`, and `conversation_sessions`.
3. Set `DATABASE_URL=postgresql://user:password@host:5432/kisan_hita`.

---

## 4. Environment Variables Reference

| Variable | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `PORT` | Integer | `8000` | Port for Uvicorn to bind |
| `HOST` | String | `0.0.0.0` | Host address |
| `DATABASE_PATH` | String | `kisan_hita.db` | File path for SQLite database |
| `ALLOWED_ORIGINS` | String | Localhost origins | Explicit comma-separated CORS origins; wildcard is not allowed with credentialed sessions |
| `COOKIE_SECURE` | Boolean | `false` | Set `true` for HTTPS production cookies |
| `GEMINI_API_KEY` | Secret | `""` | Google AI Studio Gemini API key |
| `GEMINI_MODEL` | String | `gemini-2.5-flash` | Gemini model name |
| `GEMINI_ENABLED` | Boolean | `true` | Toggle Gemini AI reasoning |
| `GNANI_LIVE_ENABLED` | Boolean | `false` | **Keep false** to protect ~5,000 balance |
| `GNANI_API_KEY` | Secret | `""` | Gnani API Key (dormant) |
| `GNANI_TOKEN` | Secret | `""` | Gnani Token (dormant) |

---

## 5. Health Checks & Monitoring

The backend exposes two specialized monitoring endpoints:

### Liveness Probe (`/api/health`)
Returns immediate HTTP 200 indicating the ASGI server is up:
```bash
curl -i http://localhost:8000/api/health
```
```json
{
  "status": "healthy",
  "app": "Kisan Hita",
  "version": "1.0.0",
  "gnani_live_enabled": false
}
```

### Readiness Probe (`/api/ready`)
Verifies SQLite connectivity and filesystem writability. Used by container orchestrators to route traffic:
```bash
curl -i http://localhost:8000/api/ready
```
```json
{
  "status": "ready",
  "database": "connected",
  "storage": "writable",
  "gemini_configured": true,
  "gnani_live_enabled": false,
  "app": "Kisan Hita",
  "version": "1.0.0",
  "timestamp": "2026-11-04T15:00:00Z"
}
```
*If database is unreachable or disk is full/read-only, `/api/ready` returns **HTTP 503 Service Unavailable**.*

---

## 6. Verification & Smoke Testing

Run the following test suite before and after every production release:

```bash
# 1. Run all backend tests
python3 -m unittest discover -s backend/tests

# 2. Test readiness endpoint
curl -s http://127.0.0.1:8000/api/ready | jq .

# 3. Test market prices query
curl -s -X POST http://127.0.0.1:8000/api/market-prices/search \
  -H "Content-Type: application/json" \
  -d '{"commodity":"Chilli","district":"Warangal","language":"te"}' | jq .

# 4. Test crop advisor recommendation
curl -s -X POST http://127.0.0.1:8000/api/crop-advisor/recommend \
  -H "Content-Type: application/json" \
  -d '{"soil_type":"Black Cotton Soil","water_availability":"Good irrigation","growing_season":"Kharif (Monsoon)","district":"Warangal"}' | jq .
```

---

## 7. Rollback & Troubleshooting Procedures

- **DNS or Network Timeouts on Outbound Calls**:
  If the backend cannot reach Gemini, verify DNS settings (`/etc/resolv.conf`) and outbound egress firewall rules on port 443.
- **Database Locked / Write Failures**:
  Verify write permissions on the directory hosting `kisan_hita.db`. If using Docker, ensure the mount volume has UID 1000 permissions (`chown -R 1000:1000 /data`).
- **Gemini Key Rate Limiting**:
  If Gemini API returns 429 (Rate Limit Exceeded), the assistant orchestrator automatically falls back to deterministic slot filling and template responses so farmers receive uninterrupted service.

