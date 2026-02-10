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
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str.strip() == "[DONE]":
                            break
                        try:
                            chunk_data = json.loads(data_str)
                            content = chunk_data.get("choices", [{}])[0].get("delta", {}).get("content", "")
                            if content:
                                yield f"data: {json.dumps({'content': content})}\n\n"
                        except:
                            continue
                
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
    except Exception as e:
        logger.error(f"Fallback AI Error: {e}")
        yield f"data: {json.dumps({'error': str(e)})}\n\n"

# --- STAP 4: De Chatbot Proxy ---
@app.post("/chatbot")
@app.post("/api/chatbot")
async def handle_chatbot(request: Request):
    logger.info("Chatbot request received in index.py")
    
    try:
        body = await request.json()
        user_input_text = body.get("input", "")
        history = body.get("history", [])
        
        # Systeem prompt opbouwen
        messages = [{"role": "system", "content": "You are DUB5, a professional AI assistant."}]
        for msg in history:
            if isinstance(msg, dict) and "role" in msg and "content" in msg:
                messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": user_input_text})

        # We proberen de zware modules te laden, maar als dat faalt gaan we direct naar fallback
        try:
            # Voeg paden toe voor import
            api_dir = Path(__file__).parent.absolute()
            root_dir = api_dir.parent.absolute()
            
            if str(api_dir) not in sys.path:
                sys.path.insert(0, str(api_dir))
            if str(root_dir) not in sys.path:
                sys.path.insert(0, str(root_dir))
            
            # Alleen proberen te importeren als we niet op Vercel crashen
            import importlib
            try:
                chatbot_mod = importlib.import_module("chatbot")
            except ImportError:
                chatbot_mod = importlib.import_module("api.chatbot")
            
            logger.info("Successfully loaded heavy chatbot module")
            
            # Controleer of we alle benodigde attributen hebben
            if hasattr(chatbot_mod, 'chatbot_response') and hasattr(chatbot_mod, 'UserInput'):
                user_input_obj = chatbot_mod.UserInput(**body)
                return await chatbot_mod.chatbot_response(user_input_obj, request)
            else:
                raise AttributeError("Chatbot module loaded but missing required functions")
            
        except Exception as e:
            logger.warning(f"Heavy module failed or too slow: {e}. Switching to Ultra-Light Fallback.")
            # Fallback naar directe Pollinations API
            return StreamingResponse(
                fallback_pollinations_ai(messages),
                media_type="text/event-stream",
                headers={
                    "Content-Type": "text/event-stream",
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive"
                }
            )

    except Exception as e:
        logger.error(f"Global Proxy Error: {e}")
        return Response(
            content=json.dumps({"error": str(e), "trace": traceback.format_exc()}),
            status_code=500,
            media_type="application/json"
        )

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
