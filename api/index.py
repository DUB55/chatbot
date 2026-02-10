import os
import sys
import time
import json
import logging
import traceback
from pathlib import Path
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Versie van de backend
VERSION = "1.1.1"

# --- STAP 1: Initialiseer FastAPI direct (geen zware imports eerst) ---
# Zorg dat we zowel de root als /api ondersteunen
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- STAP 2: Definieer Systeem Status Check die ALTIJD werkt ---
@app.get("/system-status")
@app.get("/api/system-status")
@app.get("/api/v1/status")
@app.get("/")
async def system_status(request: Request):
    return {
        "status": "online",
        "version": VERSION,
        "environment": "vercel" if os.environ.get("VERCEL") else "local",
        "python_version": sys.version,
        "path": sys.path,
        "cwd": os.getcwd(),
        "modules_loaded": CHATBOT_MODULES is not None
    }

# --- STAP 3: Probeer zware modules pas bij aanvraag of later te laden ---
# Dit voorkomt dat de hele app crasht bij het opstarten
def load_heavy_modules():
    try:
        # Voeg de root van het project EN de api map toe aan sys.path
        api_dir = Path(__file__).parent.absolute()
        root_dir = api_dir.parent.absolute()
        
        if str(api_dir) not in sys.path:
            sys.path.insert(0, str(api_dir))
        if str(root_dir) not in sys.path:
            sys.path.insert(0, str(root_dir))

        logger.info(f"Loading heavy modules from {api_dir}...")
        
        # Importeer chatbot logica van chatbot.py
        # We proberen verschillende importstijlen
        try:
            import chatbot
            logger.info("Imported chatbot module successfully")
        except ImportError as e:
            logger.warning(f"Failed to import chatbot normally, trying api.chatbot: {e}")
            import api.chatbot as chatbot
            logger.info("Imported api.chatbot module successfully")
        
        return {
            "chatbot_response": chatbot.chatbot_response,
            "UserInput": chatbot.UserInput,
            "LibraryUpload": chatbot.LibraryUpload,
            "ImageInput": chatbot.ImageInput,
            "upload_to_library": chatbot.upload_to_library,
            "get_user_library": chatbot.get_user_library,
            "delete_from_library": chatbot.delete_from_library,
            "list_library": chatbot.list_library,
            "generate_image_api": chatbot.generate_image_api,
            "favicon": chatbot.favicon,
            "serve_image_frontend": chatbot.serve_image_frontend,
            "serve_chatbot_explicit": chatbot.serve_chatbot_explicit,
            "serve_frontend": chatbot.serve_frontend
        }
    except Exception as e:
        logger.error(f"CRITICAL: Error loading chatbot modules: {e}")
        logger.error(traceback.format_exc())
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
    logger.info("Chatbot request received")
    modules = get_chatbot_modules()
    if not modules:
        logger.error("Failed to load chatbot modules")
        return Response(
            content=json.dumps({"error": "Chatbot modules failed to load. Check Vercel logs for CRITICAL errors."}),
            status_code=503,
            media_type="application/json"
        )
    
    try:
        body = await request.json()
        # Log limited body for security
        logger.info(f"Body received: {list(body.keys())}")
        
        # Gebruik de UserInput class van chatbot.py om te valideren
        try:
            user_input = modules["UserInput"](**body)
        except Exception as ve:
            logger.error(f"Validation Error: {ve}")
            return Response(
                content=json.dumps({"error": f"Validation Error: {str(ve)}"}),
                status_code=400,
                media_type="application/json"
            )
            
        # Roep de originele chatbot_response aan
        response = await modules["chatbot_response"](user_input, request)
        return response
    except Exception as e:
        logger.error(f"Proxy Chatbot Error: {e}")
        logger.error(traceback.format_exc())
        return Response(
            content=json.dumps({
                "error": "Internal Server Error in Proxy",
                "message": str(e),
                "trace": traceback.format_exc() if os.environ.get("VERCEL") else "Check logs"
            }),
            status_code=500,
            media_type="application/json"
        )

@app.post("/api/library/upload")
async def proxy_upload(upload_data: dict):
    modules = get_chatbot_modules()
    if modules:
        try:
            upload_obj = modules["LibraryUpload"](**upload_data)
            return await modules["upload_to_library"](upload_obj)
        except Exception as e:
            return {"error": str(e)}
    return {"error": "Modules not loaded"}

@app.get("/api/library/list")
async def proxy_list(user_id: str = "default_user"):
    modules = get_chatbot_modules()
    if modules:
        try:
            return await modules["list_library"](user_id)
        except Exception as e:
            return {"error": str(e)}
    return {"error": "Modules not loaded"}

@app.post("/api/image")
async def proxy_image(image_data: dict):
    modules = get_chatbot_modules()
    if modules:
        try:
            image_obj = modules["ImageInput"](**image_data)
            return await modules["generate_image_api"](image_obj)
        except Exception as e:
            return {"error": str(e)}
    return {"error": "Modules not loaded"}

@app.get("/favicon.ico")
async def proxy_favicon():
    modules = get_chatbot_modules()
    if modules: return await modules["favicon"]()
    return Response(status_code=204)

# Voor Vercel is 'app' de export die hij zoekt
