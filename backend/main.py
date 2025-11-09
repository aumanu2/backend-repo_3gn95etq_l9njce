from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, Optional
from bs4 import BeautifulSoup
import requests

from database import create_document, get_documents, collection
from schemas import Visit, Stat, Contacts

app = FastAPI(title="BeeQuest API")

# Allow all origins for preview sandbox
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/test")
async def test():
    # Simple ping + db check
    try:
        collection("visit").estimated_document_count()
        db_ok = True
    except Exception:
        db_ok = False
    return {"ok": True, "db": db_ok}

@app.post("/api/visit")
async def track_visit(req: Request, payload: Optional[Visit] = None):
    ua = req.headers.get("user-agent")
    path = "/"
    try:
        if payload and getattr(payload, "path", None):
            path = payload.path
    except Exception:
        pass
    try:
        create_document("visit", {"path": path, "user_agent": ua})
    except Exception:
        # Even if db fails, we return success to avoid blocking UI
        pass
    return {"ok": True}

@app.get("/api/stats", response_model=Stat)
async def stats():
    try:
        total = collection("visit").estimated_document_count()
    except Exception:
        total = 0
    return {"total_visits": total}

class ImportBody(BaseModel):
    url: str

@app.post("/api/import-contacts", response_model=Contacts)
async def import_contacts(body: ImportBody):
    try:
        r = requests.get(body.url, timeout=8)
        r.raise_for_status()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch source: {e}")

    soup = BeautifulSoup(r.text, "html.parser")

    data: Dict[str, Any] = {}

    # Heuristics: look for anchors matching platforms
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        low = href.lower()
        if "instagram.com" in low and "instagram" not in data:
            data["instagram"] = href
        if ("wa.me" in low or "whatsapp" in low) and "whatsapp" not in data:
            data["whatsapp"] = href
        if href.startswith("mailto:") and "email" not in data:
            data["email"] = href.replace("mailto:", "")
        if ("twitter.com" in low or "x.com" in low) and "x" not in data:
            data["x"] = href

    return data
