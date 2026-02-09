import json
import os
import time
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

class JSONDatabase:
    """
    Een simpele JSON-gebaseerde database voor persistente opslag op Vercel (via /tmp) 
    of lokaal. Slaat leermateriaal en metadata op.
    """
    
    def __init__(self):
        # Op Vercel is /tmp de enige beschrijfbare map
        if os.path.exists("/tmp"):
            self.db_path = Path("/tmp/dub5_knowledge_base.json")
        else:
            self.db_path = Path(__file__).parent.parent / "data" / "knowledge_base.json"
            
        # Zorg dat de data map bestaat
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.data = self._load()

    def _load(self) -> Dict[str, Any]:
        if self.db_path.exists():
            try:
                with open(self.db_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Fout bij laden database: {e}")
        return {
            "libraries": {},  # user_id -> { library_id -> { metadata, chunks } }
            "projects": {},   # session_id -> { files, context }
            "global_knowledge": []
        }

    def _save(self):
        try:
            with open(self.db_path, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Fout bij opslaan database: {e}")

    def add_to_library(self, user_id: str, title: str, content: str, chunks: List[str], metadata: Dict = None):
        if user_id not in self.data["libraries"]:
            self.data["libraries"][user_id] = {}
            
        lib_id = hashlib_id(f"{user_id}:{title}")
        self.data["libraries"][user_id][lib_id] = {
            "id": lib_id,
            "title": title,
            "content_summary": content[:500] + "...",
            "chunks": chunks,
            "metadata": metadata or {},
            "created_at": time.time()
        }
        self._save()
        return lib_id

    def get_library(self, user_id: str) -> List[Dict]:
        user_libs = self.data["libraries"].get(user_id, {})
        return list(user_libs.values())

    def delete_from_library(self, user_id: str, lib_id: str):
        if user_id in self.data["libraries"] and lib_id in self.data["libraries"][user_id]:
            del self.data["libraries"][user_id][lib_id]
            self._save()
            return True
        return False

    def update_project_state(self, session_id: str, project_data: Dict):
        self.data["projects"][session_id] = {
            "data": project_data,
            "updated_at": time.time()
        }
        self._save()

    def get_project_state(self, session_id: str) -> Optional[Dict]:
        return self.data["projects"].get(session_id)

def hashlib_id(text: str) -> str:
    import hashlib
    return hashlib.md5(text.encode('utf-8')).hexdigest()[:12]

# Singleton instance
db = JSONDatabase()
