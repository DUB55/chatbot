import os
import sys
import time
import json
import logging
import traceback
from pathlib import Path
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

# Versie van de backend
VERSION = "1.1.0"

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- STAP 1: Initialiseer FastAPI direct (geen zware imports eerst) ---
app = FastAPI(root_path="/api" if os.environ.get("VERCEL") else "")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- STAP 2: Definieer Health Check die ALTIJD werkt ---
@app.get("/health")
@app.get("/api/health")
@app.get("/")
async def health_check(request: Request):
    return {
        "status": "ok",
        "version": VERSION,
        "environment": "vercel" if os.environ.get("VERCEL") else "local",
        "url": str(request.url),
        "timestamp": time.time()
    }

# --- STAP 3: Probeer zware modules pas bij aanvraag of later te laden ---
# Dit voorkomt dat de hele app crasht bij het opstarten
def load_heavy_modules():
    try:
        # Voeg de huidige map toe aan sys.path voor imports
        current_dir = Path(__file__).parent.absolute()
        if str(current_dir) not in sys.path:
            sys.path.append(str(current_dir))

        # Importeer chatbot logica van chatbot.py (het originele bestand)
        # We proberen zowel absolute als relatieve imports
        try:
            from api.chatbot import chatbot_response, UserInput, LibraryUpload, ImageInput, upload_to_library, get_user_library, delete_from_library, list_library, generate_image_api, favicon, serve_image_frontend, serve_chatbot_explicit, serve_frontend as original_serve_frontend
        except ImportError:
            from chatbot import chatbot_response, UserInput, LibraryUpload, ImageInput, upload_to_library, get_user_library, delete_from_library, list_library, generate_image_api, favicon, serve_image_frontend, serve_chatbot_explicit, serve_frontend as original_serve_frontend
        
        return {
            "chatbot_response": chatbot_response,
            "UserInput": UserInput,
            "LibraryUpload": LibraryUpload,
            "ImageInput": ImageInput,
            "upload_to_library": upload_to_library,
            "get_user_library": get_user_library,
            "delete_from_library": delete_from_library,
            "list_library": list_library,
            "generate_image_api": generate_image_api,
            "favicon": favicon,
            "serve_image_frontend": serve_image_frontend,
            "serve_chatbot_explicit": serve_chatbot_explicit,
            "serve_frontend": original_serve_frontend
        }
    except Exception as e:
        logger.error(f"Error loading original chatbot modules: {e}")
        traceback.print_exc()
        return None

# Globale cache voor modules
CHATBOT_MODULES = None

def get_chatbot_modules():
    global CHATBOT_MODULES
    if CHATBOT_MODULES is None:
        CHATBOT_MODULES = load_heavy_modules()
    return CHATBOT_MODULES

# --- STAP 4: Definieer Proxy Routes ---

@app.middleware("http")
async def global_exception_handler(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception as e:
        logger.error(f"GLOBAL ERROR: {e}")
        return Response(
            content=json.dumps({
                "error": "Internal Server Error",
                "message": str(e),
                "trace": traceback.format_exc()
            }),
            status_code=500,
            media_type="application/json"
        )

@app.post("/chatbot")
@app.post("/api/chatbot")
async def handle_chatbot(request: Request):
    modules = get_chatbot_modules()
    if not modules:
        return {"error": "Chatbot modules failed to load on Vercel. Check logs."}
    
    try:
        body = await request.json()
        user_input = modules["UserInput"](**body)
        return await modules["chatbot_response"](user_input, request)
    except Exception as e:
        logger.error(f"Proxy Chatbot Error: {e}")
        return {"error": str(e), "trace": traceback.format_exc()}

@app.post("/api/library/upload")
async def proxy_upload(upload_data: dict):
    modules = get_chatbot_modules()
    if modules:
        upload_obj = modules["LibraryUpload"](**upload_data)
        return await modules["upload_to_library"](upload_obj)
    return {"error": "Modules not loaded"}

@app.get("/api/library/list")
async def proxy_list(user_id: str = "default_user"):
    modules = get_chatbot_modules()
    if modules:
        return await modules["list_library"](user_id)
    return {"error": "Modules not loaded"}

@app.post("/api/image")
async def proxy_image(image_data: dict):
    modules = get_chatbot_modules()
    if modules:
        image_obj = modules["ImageInput"](**image_data)
        return await modules["generate_image_api"](image_obj)
    return {"error": "Modules not loaded"}

@app.get("/favicon.ico")
async def proxy_favicon():
    modules = get_chatbot_modules()
    if modules: return await modules["favicon"]()
    return Response(status_code=204)

# Voor Vercel is 'app' de export die hij zoekt
