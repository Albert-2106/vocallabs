# Vocal — Cold Outreach Pipeline (Connected)

## What's included

```
vocal_app/
├── server.py                    ← NEW: FastAPI server (bridges frontend ↔ backend)
├── vocal_pipeline_connected.html ← UPDATED: frontend calls the real backend
├── start.sh                     ← Convenience startup script
├── main.py                      ← Original CLI (still works standalone)
├── .env                         ← Your API keys
└── stages/
    ├── company_finder.py
    ├── lead_finder.py
    ├── email_resolver.py
    └── email_sender.py
```

## Quick Start

### 1. Install dependencies
```bash
pip install fastapi uvicorn sse-starlette python-dotenv requests
```

### 2. Start the backend server
```bash
cd vocal_app
uvicorn server:app --reload --port 8000
```
Or just run: `./start.sh`

### 3. Open the frontend
Open `vocal_pipeline_connected.html` in your browser (double-click or drag into Chrome/Firefox).

### 4. Run the pipeline
- Enter a seed domain (e.g., `openai.com`)
- Click **Run Pipeline**
- Watch real data stream in from your backend

## How it works

The original HTML had a **fake simulation** that generated random company/lead data in the browser. The connected version replaces that with real API calls:

```
Browser HTML  ──POST /run──►  FastAPI server  ──calls──►  stages/*.py
              ◄──SSE stream──                             (Hunter, SerpAPI, etc.)
```

The backend streams results back as **Server-Sent Events (SSE)**, so the terminal log, tables, and progress indicators all update in real-time just like the simulation did — except with actual data.

## API Keys (.env)

| Key | Free tier | Used for |
|-----|-----------|----------|
| `SERPAPI_KEY` | 100/month | Company discovery |
| `HUNTER_API_KEY` | 25/month | Lead + email finder |
| `SMTP_EMAIL` + `SMTP_APP_PASSWORD` | Gmail free | Sending emails |

All keys are optional — the pipeline has fallbacks for everything.

## Backend API

`POST /run` — starts the pipeline and streams SSE events:

| Event | Payload |
|-------|---------|
| `log` | `{msg, type}` |
| `api_status` | `{apis: {name: bool}}` |
| `stage` | `{stage: 0-3, status: active\|done\|error}` |
| `companies` | `{companies: [...]}` |
| `leads` | `{leads: [...]}` |
| `resolved` | `{resolved: [...]}` |
| `dispatch` | `{sendResults: [...]}` |
| `done` | `{success: bool, error?: string}` |

`GET /health` — returns `{"status": "ok"}`
