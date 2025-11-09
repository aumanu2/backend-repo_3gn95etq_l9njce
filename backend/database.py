import os
from typing import Any, Dict, List, Optional
from pymongo import MongoClient
from pymongo.collection import Collection

DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("MONGODB_URI") or "mongodb://localhost:27017"
DATABASE_NAME = os.getenv("DATABASE_NAME") or "appdb"

_client: Optional[MongoClient] = None
_db = None

def get_db():
    global _client, _db
    if _db is None:
        _client = MongoClient(DATABASE_URL)
        _db = _client[DATABASE_NAME]
    return _db

# Convenience alias used by app modules
_db_cached = get_db()

def collection(name: str) -> Collection:
    return _db_cached[name]

# Helper utilities similar to those in the platform description
from datetime import datetime

def create_document(collection_name: str, data: Dict[str, Any]) -> str:
    col = collection(collection_name)
    now = datetime.utcnow()
    data = {**data, "created_at": now, "updated_at": now}
    res = col.insert_one(data)
    return str(res.inserted_id)


def get_documents(collection_name: str, filter_dict: Optional[Dict[str, Any]] = None, limit: int = 50) -> List[Dict[str, Any]]:
    col = collection(collection_name)
    cur = col.find(filter_dict or {}).limit(limit)
    return list(cur)
