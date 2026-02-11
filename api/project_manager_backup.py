import logging
from typing import Dict, List, Optional
from database import db

logger = logging.getLogger(__name__)

class ProjectStateManager:
    """
    Beheert de staat van een project dat door de AI Web App Builder wordt gebouwd.
    Houdt bij welke bestanden er zijn gemaakt en wat hun inhoud is.
    """
    
    def __init__(self):
        pass

    def get_project_context(self, session_id: str) -> str:
        """
        Genereert een overzicht van de huidige projectstructuur voor de AI.
        """
        state = db.get_project_state(session_id)
        if not state or "data" not in state:
            return "Geen bestaand project gevonden in deze sessie."
            
        files = state["data"].get("files", {})
        if not files:
            return "Project is leeg."
            
        context = "HUIDIGE PROJECTSTRUCTUUR:\n"
        for path, content in files.items():
            context += f"- {path} ({len(content)} tekens)\n"
            
        return context

    def update_file(self, session_id: str, path: str, content: str):
        """
        Voegt een bestand toe of werkt het bij in de projectstaat.
        """
        state = db.get_project_state(session_id) or {"data": {"files": {}}}
        if "files" not in state["data"]:
            state["data"]["files"] = {}
            
        state["data"]["files"][path] = content
        db.update_project_state(session_id, state["data"])

    def get_file_content(self, session_id: str, path: str) -> Optional[str]:
        state = db.get_project_state(session_id)
        if state and "data" in state:
            return state["data"].get("files", {}).get(path)
        return None

# Singleton instance
project_manager = ProjectStateManager()
