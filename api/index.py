import json
import logging
import httpx
import asyncio
import urllib.parse
import sys
import os
from typing import AsyncGenerator
from fastapi import FastAPI, Request, Response
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

# Uitgebreide logging voor Vercel diagnose
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger("DUB5-Backend")

app = FastAPI(title="DUB5 AI Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# DEBUG: Log environment info bij opstarten
logger.info(f"Python Version: {sys.version}")
logger.info(f"Current Directory: {os.getcwd()}")
logger.info(f"Directory Contents: {os.listdir('.')}")

async def simple_pollinations_stream(user_query: str) -> AsyncGenerator[str, None]:
    """
    Ultra-stabiele stream die DIRECT de Pollinations API aanroept.
    Geen complexe filters, geen zware libraries.
    """
    try:
        system_prompt = "You are DUB5 AI, a helpful assistant. Answer in Dutch if the user speaks Dutch."
        encoded_query = urllib.parse.quote(user_query)
        encoded_system = urllib.parse.quote(system_prompt)
        
        # We gebruiken de GET stream interface van Pollinations (zeer robuust)
        url = f"https://text.pollinations.ai/{encoded_query}?model=openai&system={encoded_system}"
        
        logger.info(f"Connecting to Pollinations: {url[:100]}...")
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream("GET", url) as response:
                if response.status_code != 200:
                    err_msg = f"Pollinations Error {response.status_code}"
                    logger.error(err_msg)
                    yield f"data: {json.dumps({'error': err_msg})}\n\n"
                    return
                
                # Metadata sturen voor frontend tracking
                yield f"data: {json.dumps({'type': 'metadata', 'model': 'pollinations-direct'})}\n\n"
                
                async for chunk in response.aiter_text():
                    if chunk:
                        # Directe tekst doorsturen in content wrapper
                        yield f"data: {json.dumps({'content': chunk})}\n\n"
                
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
                logger.info("Stream completed successfully")
                
    except Exception as e:
        logger.error(f"Fatal Stream Error: {str(e)}", exc_info=True)
        yield f"data: {json.dumps({'error': f'Systeemfout: {str(e)}'})}\n\n"

@app.get("/")
async def root():
    return {
        "status": "online",
        "message": "DUB5 AI Backend is active",
        "env": {
            "python": sys.version.split()[0],
            "cwd": os.getcwd()
        }
    }

@app.get("/api/ping")
async def ping():
    """Test endpoint om connectiviteit te verifiëren."""
    return {"ping": "pong", "timestamp": asyncio.get_event_loop().time()}

@app.get("/api/system-status")
@app.get("/status")
async def status():
    return {"status": "ok", "mode": "production", "engine": "pollinations-direct"}

@app.get("/api/library/list")
async def list_libraries():
    return {"libraries": [], "message": "Library mode disabled for stability"}

@app.get("/favicon.ico")
async def favicon():
    return Response(status_code=204)

@app.post("/api/chatbot")
@app.post("/chatbot")
async def chatbot_proxy(request: Request):
    logger.info("--- New Chatbot Request ---")
    
    try:
        # Veilige body parsing
        raw_body = await request.body()
        logger.info(f"Raw body length: {len(raw_body)} bytes")
        
        try:
            body = json.loads(raw_body.decode('utf-8'))
        except Exception as e:
            logger.warning(f"JSON Parse failed: {e}. Using default.")
            body = {"input": "Hallo"}
        
        user_input = body.get("input", "Hallo")
        logger.info(f"User input: {user_input[:50]}...")
        
        return StreamingResponse(
            simple_pollinations_stream(user_input),
            media_type="text/event-stream",
            headers={
                "X-Accel-Buffering": "no",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*"
            }
        )
        
    except Exception as e:
        logger.error(f"Chatbot Proxy Crash: {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=500, 
            content={
                "error": "Backend Crash", 
                "detail": str(e),
                "type": "fatal_proxy_error"
            }
        )

# Vercel entry point
# De variabele 'app' moet op het top-level staan

# Voor Vercel is 'app' de export die hij zoekt
