"""
Vocal Outreach Pipeline – FastAPI Server
Run:  uvicorn server:app --reload --port 8000
"""

import sys, os, json, asyncio
from datetime import datetime
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# Make stages importable
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from stages.company_finder import find_similar_companies
from stages.lead_finder    import find_leads
from stages.email_resolver import resolve_emails

app = FastAPI(title="Vocal Outreach API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class RunRequest(BaseModel):
    seed_domain: str
    limit: int = 5
    per_co: int = 2


def sse(event: str, data: dict) -> str:
    """Format a server-sent event."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


async def run_pipeline_stream(req: RunRequest):
    seed = (req.seed_domain.strip().lower()
            .replace("https://", "").replace("http://", "").split("/")[0])

    yield sse("log", {"msg": f"Seed domain: {seed}", "type": ""})
    yield sse("log", {"msg": f"Limit: {req.limit} companies × {req.per_co} contacts", "type": ""})
    await asyncio.sleep(0.1)

    # ── Stage 1: Company Discovery ────────────────────────────────────────────
    yield sse("stage", {"stage": 0, "status": "active"})
    yield sse("log", {"msg": "[Stage 1/4] Company Discovery", "type": "ok"})
    await asyncio.sleep(0.05)

    try:
        companies = await asyncio.get_event_loop().run_in_executor(
            None, find_similar_companies, seed, req.limit
        )
    except Exception as e:
        yield sse("log", {"msg": f"Error in company discovery: {e}", "type": "err"})
        yield sse("stage", {"stage": 0, "status": "error"})
        yield sse("done", {"error": str(e)})
        return

    if not companies:
        yield sse("log", {"msg": "No companies discovered.", "type": "err"})
        yield sse("stage", {"stage": 0, "status": "error"})
        yield sse("done", {"error": "No companies found"})
        return

    for co in companies:
        yield sse("log", {"msg": f"  ✓ {co['name']:<26} {co['domain']:<28} [{co.get('source','?')}]", "type": "ok"})
        await asyncio.sleep(0.02)

    yield sse("companies", {"companies": companies})
    yield sse("log", {"msg": f"  → {len(companies)} companies found", "type": "dim"})
    yield sse("stage", {"stage": 0, "status": "done"})
    await asyncio.sleep(0.1)

    # ── Stage 2: Lead Discovery ───────────────────────────────────────────────
    yield sse("stage", {"stage": 1, "status": "active"})
    yield sse("log", {"msg": "[Stage 2/4] Lead / Decision-Maker Discovery", "type": "ok"})
    await asyncio.sleep(0.05)

    try:
        leads = await asyncio.get_event_loop().run_in_executor(
            None, find_leads, companies, req.per_co
        )
    except Exception as e:
        yield sse("log", {"msg": f"Error in lead discovery: {e}", "type": "err"})
        yield sse("stage", {"stage": 1, "status": "error"})
        yield sse("done", {"error": str(e)})
        return

    for lead in leads:
        li_str = "LinkedIn✓" if lead.get("linkedin") else "no LinkedIn"
        yield sse("log", {"msg": f"  ✓ {lead['name']:<26} {lead['role']:<24} {li_str}", "type": "ok"})
        await asyncio.sleep(0.02)

    yield sse("leads", {"leads": leads})
    yield sse("log", {"msg": f"  → {len(leads)} leads found", "type": "dim"})
    yield sse("stage", {"stage": 1, "status": "done"})
    await asyncio.sleep(0.1)

    # ── Stage 3: Email Resolution ─────────────────────────────────────────────
    yield sse("stage", {"stage": 2, "status": "active"})
    yield sse("log", {"msg": "[Stage 3/4] Email Resolution & Verification", "type": "ok"})
    await asyncio.sleep(0.05)

    try:
        resolved = await asyncio.get_event_loop().run_in_executor(
            None, resolve_emails, leads
        )
    except Exception as e:
        yield sse("log", {"msg": f"Error in email resolution: {e}", "type": "err"})
        yield sse("stage", {"stage": 2, "status": "error"})
        yield sse("done", {"error": str(e)})
        return

    for r in resolved:
        conf = r.get("email_confidence", 0)
        ver = "verified" if r.get("email_verified") else f"~{conf}%"
        mx = "mx✓" if r.get("mx_valid") else "mx✗"
        t = "ok" if conf >= 70 else "warn" if conf >= 40 else "err"
        yield sse("log", {"msg": f"  {r.get('name','?'):<26} → {r.get('email','—'):<38} {ver}  {mx}", "type": t})
        await asyncio.sleep(0.02)

    yield sse("resolved", {"resolved": resolved})
    yield sse("log", {"msg": f"  → {len(resolved)} emails resolved", "type": "dim"})
    yield sse("stage", {"stage": 2, "status": "done"})
    yield sse("log", {"msg": "Pipeline complete!", "type": "ok"})

    # Save run
    os.makedirs(os.path.join(os.path.dirname(__file__), "runs"), exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = os.path.join(os.path.dirname(__file__), f"runs/{seed.replace('.','_')}_{ts}.json")
    with open(fname, "w") as f:
        json.dump({
            "seed": seed, "companies": companies, "leads": leads,
            "resolved": resolved,
            "finished_at": datetime.now().isoformat()
        }, f, indent=2, default=str)

    yield sse("done", {"success": True, "run_file": fname})


@app.post("/run")
async def run_pipeline(req: RunRequest):
    return StreamingResponse(
        run_pipeline_stream(req),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/health")
def health():
    return {"status": "ok"}
