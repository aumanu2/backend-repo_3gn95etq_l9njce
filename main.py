import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
from typing import Dict, List, Optional
import re
import requests
from bs4 import BeautifulSoup

from database import db

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SITE_KEY = "beequest"
COLLECTION = "sitestat"

class StatResponse(BaseModel):
    name: str
    total_visits: int

class ImportRequest(BaseModel):
    url: HttpUrl

class ContactsResponse(BaseModel):
    instagram: Optional[str] = None
    whatsapp: Optional[str] = None
    email: Optional[str] = None
    x: Optional[str] = None

class ContentSection(BaseModel):
    title: Optional[str] = None
    subtitle: Optional[str] = None
    points: Optional[List[str]] = []

class ContentResponse(BaseModel):
    source: str
    title: Optional[str] = None
    description: Optional[str] = None
    highlights: List[Dict[str, Optional[str]]] = []
    sections: List[ContentSection] = []

@app.get("/")
def read_root():
    return {"message": "Hello from FastAPI Backend!"}

@app.get("/api/hello")
def hello():
    return {"message": "Hello from the backend API!"}

@app.get("/api/stats", response_model=StatResponse)
def get_stats():
    if db is None:
        return {"name": SITE_KEY, "total_visits": 0}
    doc = db[COLLECTION].find_one({"name": SITE_KEY})
    total = int(doc.get("total_visits", 0)) if doc else 0
    return {"name": SITE_KEY, "total_visits": total}

@app.post("/api/visit", response_model=StatResponse)
def add_visit():
    """Increment total visit counter and return current stats"""
    if db is None:
        return {"name": SITE_KEY, "total_visits": 0}
    res = db[COLLECTION].find_one_and_update(
        {"name": SITE_KEY},
        {"$inc": {"total_visits": 1}},
        upsert=True,
        return_document=True
    )
    if not res:
        res = db[COLLECTION].find_one({"name": SITE_KEY})
    total = int(res.get("total_visits", 0)) if res else 0
    return {"name": SITE_KEY, "total_visits": total}

@app.post("/api/import-contacts", response_model=ContactsResponse)
def import_contacts(payload: ImportRequest):
    """Fetch a webpage and extract common contact links: Instagram, WhatsApp, Email, X/Twitter."""
    try:
        resp = requests.get(str(payload.url), timeout=10)
        resp.raise_for_status()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch URL: {e}")

    soup = BeautifulSoup(resp.text, 'html.parser')
    links = [a.get('href') for a in soup.find_all('a') if a.get('href')]

    instagram = next((l for l in links if re.search(r"instagram\.com/", l, re.I)), None)
    whatsapp = next((l for l in links if re.search(r"wa\.me/|api\.whatsapp\.com/|whatsapp\.com/send", l, re.I)), None)
    email = next((l for l in links if l.lower().startswith('mailto:')), None)
    xlink = next((l for l in links if re.search(r"twitter\.com/|x\.com/", l, re.I)), None)

    # Normalize email to address only
    if email and email.lower().startswith('mailto:'):
        email = email.split(':', 1)[1].split('?')[0]

    return {
        "instagram": instagram,
        "whatsapp": whatsapp,
        "email": email,
        "x": xlink,
    }

@app.post("/api/import-content", response_model=ContentResponse)
def import_content(payload: ImportRequest):
    """Fetch a webpage and extract structured textual content suitable for premium templates."""
    try:
        resp = requests.get(str(payload.url), timeout=12)
        resp.raise_for_status()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch URL: {e}")

    soup = BeautifulSoup(resp.text, 'html.parser')

    # Title & description
    title = None
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
    desc_tag = soup.find('meta', attrs={'name': 'description'}) or soup.find('meta', attrs={'property': 'og:description'})
    description = desc_tag['content'].strip() if (desc_tag and desc_tag.get('content')) else None

    # Collect headings and paragraphs
    blocks: List[Dict[str, str]] = []
    for tag in soup.find_all(['h1', 'h2', 'h3', 'p', 'li']):
        text = tag.get_text(separator=' ', strip=True)
        if not text:
            continue
        blocks.append({'tag': tag.name.lower(), 'text': text})

    # Build highlights: top few strong lines from h1/p near start
    highlights: List[Dict[str, Optional[str]]] = []
    for b in blocks[:40]:
        if b['tag'] in ('h1', 'h2'):
            highlights.append({'title': b['text'], 'text': None})
        elif b['tag'] == 'p' and len(b['text'].split()) > 6:
            highlights.append({'title': b['text'][:120] + ('…' if len(b['text']) > 120 else ''), 'text': None})
        if len(highlights) >= 6:
            break

    # Build sections grouped by h2/h3 with following content
    sections: List[ContentSection] = []
    current: Optional[ContentSection] = None
    for b in blocks:
        tag, text = b['tag'], b['text']
        if tag in ('h2', 'h3'):
            if current and (current.title or current.subtitle or current.points):
                sections.append(current)
            current = ContentSection(title=text, subtitle=None, points=[])
        elif tag == 'p':
            if current is None:
                current = ContentSection(title=text, points=[])
            else:
                if current.subtitle is None and len(text.split()) > 4 and (not current.points):
                    current.subtitle = text
                else:
                    (current.points or []).append(text)
        elif tag == 'li':
            if current is None:
                current = ContentSection(title='Highlights', points=[text])
            else:
                (current.points or []).append(text)
    if current and (current.title or current.subtitle or current.points):
        sections.append(current)

    # Limit sizes
    for s in sections:
        if s.points:
            s.points = s.points[:8]

    return ContentResponse(
        source=str(payload.url),
        title=title,
        description=description,
        highlights=highlights,
        sections=sections[:10]
    )

@app.get("/test")
def test_database():
    """Test endpoint to check if database is available and accessible"""
    response: Dict[str, object] = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    
    try:
        from database import db as _db
        
        if _db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = _db.name if hasattr(_db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            
            try:
                collections = _db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
            
    except ImportError:
        response["database"] = "❌ Database module not found (run enable-database first)"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"
    
    import os as _os
    response["database_url"] = "✅ Set" if _os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if _os.getenv("DATABASE_NAME") else "❌ Not Set"
    
    return response


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
