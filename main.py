import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict

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
    # When upserting, PyMongo may return None depending on driver; fetch again
    if not res:
        res = db[COLLECTION].find_one({"name": SITE_KEY})
    total = int(res.get("total_visits", 0)) if res else 0
    return {"name": SITE_KEY, "total_visits": total}

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
        # Try to import database module
        from database import db as _db
        
        if _db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = _db.name if hasattr(_db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            
            # Try to list collections to verify connectivity
            try:
                collections = _db.list_collection_names()
                response["collections"] = collections[:10]  # Show first 10 collections
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
            
    except ImportError:
        response["database"] = "❌ Database module not found (run enable-database first)"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"
    
    # Check environment variables
    import os as _os
    response["database_url"] = "✅ Set" if _os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if _os.getenv("DATABASE_NAME") else "❌ Not Set"
    
    return response


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
