import os
import sys
import time
import json
import logging
import traceback
import httpx
import asyncio
from pathlib import Path
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Versie van de backend
VERSION = "1.2.0-ULTRA-LIGHT"

# --- STAP 1: Initialiseer FastAPI direct ---
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- STAP 2: Definieer Systeem Status Check (MOET ALTIJD WERKEN) ---
@app.get("/system-status")
@app.get("/api/system-status")
@app.get("/")
async def system_status(request: Request):
    return {
        "status": "online",
        "version": VERSION,
        "environment": "vercel" if os.environ.get("VERCEL") else "local",
        "timestamp": time.time(),
        "uptime": "system is ready"
    }

# --- STAP 3: Fallback AI Logica (zonder g4f) ---
async def fallback_pollinations_ai(messages):
    """Directe HTTP aanroep naar Pollinations AI als g4f faalt."""
    try:
        logger.info("Using Fallback Pollinations AI Layer")
        async with httpx.AsyncClient(timeout=60.0) as client:
            # We sturen een streaming request
            async with client.stream(
                "POST",
                "https://text.pollinations.ai/openai",
                json={
                    "messages": messages,
                    "model": "openai",
                    "stream": True
                }
            ) as response:
                if response.status_code != 200:
                    yield f"data: {json.dumps({'error': f'Pollinations Error: {response.status_code}'})}\n\n"
                    return

                # Stuur metadata eerst
                yield f"data: {json.dumps({'type': 'metadata', 'model': 'pollinations-fallback', 'status': 'fallback'})}\n\n"
                
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                        
                    # Als de provider direct tekst stuurt zonder "data: " prefix
                    clean_line = line.strip()
                    if clean_line.startswith("data: "):
                        clean_line = clean_line[6:]
                    
                    if clean_line == "[DONE]":
                        break
                        
                    try:
                        if clean_line.startswith('{'):
                            chunk_data = json.loads(clean_line)
                            content = chunk_data.get("choices", [{}])[0].get("delta", {}).get("content", "")
                            if content:
                                yield f"data: {json.dumps({'content': content})}\n\n"
                        else:
                            # Directe tekst
                            yield f"data: {json.dumps({'content': clean_line})}\n\n"
                    except:
                        yield f"data: {json.dumps({'content': clean_line})}\n\n"
                
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
    except Exception as e:
        logger.error(f"Fallback AI Error: {e}")
        yield f"data: {json.dumps({'error': str(e)})}\n\n"

# --- STAP 4: De Chatbot Proxy ---
@app.post("/chatbot")
@app.post("/api/chatbot")
async def handle_chatbot(request: Request):
    logger.info("Chatbot request received in index.py")
    
    # Gebruik een try-except om de body veilig uit te lezen
    body = {}
    try:
        body = await request.json()
    except Exception as je:
        logger.error(f"JSON Parsing Error: {je}")
        body = {"input": "Hello", "history": []}

    user_input_text = body.get("input", "Hello")
    history = body.get("history", [])
    
    # Systeem prompt opbouwen
    messages = [{"role": "system", "content": "You are DUB5, a professional AI assistant."}]
    for msg in history:
        if isinstance(msg, dict) and "role" in msg and "content" in msg:
            messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": user_input_text})

    # ALTIJD een 200 OK StreamingResponse teruggeven om 500 errors te voorkomen
    # De generator handelt interne fouten af en stuurt die als 'data: {"error": ...}'
    return StreamingResponse(
        safe_chatbot_generator(messages, body, request),
        media_type="text/event-stream",
        headers={
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

async def safe_chatbot_generator(messages, body, request):
    """Wrapper generator die NOOIT crasht en altijd een geldige SSE stream stuurt."""
    try:
        async for chunk in attempt_chatbot_logic(messages, body, request):
            yield chunk
    except Exception as e:
        logger.error(f"Generator Error: {e}")
        error_msg = f"Systeemfout in generator: {str(e)}"
        yield f"data: {json.dumps({'error': error_msg})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

async def attempt_chatbot_logic(messages, body, request):
    """Probeert eerst de zware chatbot, anders fallback."""
    try:
        # We laden de zware modules NOOIT op Vercel om de 250MB limiet te omzeilen
        if os.environ.get("VERCEL"):
            logger.info("Vercel detected: Skipping heavy modules to avoid 250MB limit.")
            raise ImportError("Vercel size limit safety")

        # Lokale import poging
        api_dir = Path(__file__).parent.absolute()
        root_dir = api_dir.parent.absolute()
        if str(api_dir) not in sys.path: sys.path.insert(0, str(api_dir))
        if str(root_dir) not in sys.path: sys.path.insert(0, str(root_dir))
        
        # Voorkom recursieve import van api.index als chatbot
        import importlib
        chatbot_mod = None
        try:
            # Probeer eerst de chatbot in de root (lokaal)
            if (root_dir / "chatbot.py").exists():
                chatbot_mod = importlib.import_module("chatbot")
            else:
                chatbot_mod = importlib.import_module("api.chatbot")
        except Exception as im_err:
            logger.warning(f"Import failed: {im_err}. Trying api.chatbot directly.")
            chatbot_mod = importlib.import_module("api.chatbot")
        
        if chatbot_mod and hasattr(chatbot_mod, 'chatbot_response'):
            # Hier moeten we de generator van chatbot_response uitlezen
            # Omdat we al in een StreamingResponse zitten, moeten we de chunks doorgeven
            user_input_obj = chatbot_mod.UserInput(**body)
            response = await chatbot_mod.chatbot_response(user_input_obj, request)
            
            # chatbot_response geeft zelf een StreamingResponse terug
            async for chunk in response.body_iterator:
                yield chunk
            return
        else:
            raise AttributeError("Missing chatbot_response")

    except Exception as e:
        logger.warning(f"Using Fallback AI due to: {e}")
        async for chunk in fallback_pollinations_ai(messages):
            yield chunk

# Proxy routes voor andere functionaliteit (simpel gehouden)
@app.get("/api/library/list")
async def proxy_list(user_id: str = "default_user"):
    try:
        import importlib
        chatbot_mod = importlib.import_module("chatbot")
        return await chatbot_mod.list_library(user_id)
    except:
        return {"libraries": []}

@app.get("/favicon.ico")
async def favicon():
    return Response(status_code=204)

# Voor Vercel is 'app' de export die hij zoekt
