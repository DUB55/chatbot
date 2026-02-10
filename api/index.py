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

# G4F Import (Minimal)
try:
    import g4f
    # Forceer g4f om /tmp te gebruiken voor cache op Vercel
    os.environ['G4F_CACHE_DIR'] = '/tmp/.g4f_cache'
    G4F_AVAILABLE = True
except ImportError:
    G4F_AVAILABLE = False

# Uitgebreide logging
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

async def g4f_ai_stream(user_query: str, history: list) -> AsyncGenerator[str, None]:
    """Herstelde G4F AI functionaliteit (Lichtgewicht)."""
    try:
        if not G4F_AVAILABLE:
            raise ImportError("G4F library not found")

        messages = [{"role": "system", "content": "You are DUB5 AI, a helpful assistant. Answer in Dutch."}]
        for m in history[-5:]: # Alleen laatste 5 berichten voor snelheid
            if isinstance(m, dict) and "role" in m:
                messages.append({"role": m["role"], "content": m.get("content", "")})
        
        messages.append({"role": "user", "content": user_query})

        # Gebruik een stabiele provider die geen browser nodig heeft
        provider = g4f.Provider.Blackbox # Of een andere stabiele non-browser provider

        logger.info(f"Connecting to G4F (Provider: {provider.__name__})...")
        
        yield f"data: {json.dumps({'type': 'metadata', 'model': 'g4f-minimal'})}\n\n"

        # G4F Async Iterator
        response = await g4f.ChatCompletion.create_async(
            model=g4f.models.default,
            messages=messages,
            provider=provider,
            stream=True
        )

        async for chunk in response:
            if chunk:
                yield f"data: {json.dumps({'content': chunk})}\n\n"
        
        yield f"data: {json.dumps({'type': 'done'})}\n\n"
        logger.info("G4F Stream completed")

    except Exception as e:
        logger.error(f"G4F Error: {e}")
        # Automatische fallback naar Pollinations als G4F faalt
        logger.info("Falling back to Pollinations...")
        async for chunk in simple_pollinations_stream(user_query):
            yield chunk

async def simple_pollinations_stream(user_query: str) -> AsyncGenerator[str, None]:
    """Stabiele Pollinations Fallback."""
    try:
        encoded_query = urllib.parse.quote(user_query)
        url = f"https://text.pollinations.ai/{encoded_query}?model=openai&system=You%20are%20DUB5%20AI"
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            async with client.stream("GET", url) as response:
                if response.status_code == 200:
                    yield f"data: {json.dumps({'type': 'metadata', 'model': 'pollinations-fallback'})}\n\n"
                    async for chunk in response.aiter_text():
                        if chunk: yield f"data: {json.dumps({'content': chunk})}\n\n"
                    yield f"data: {json.dumps({'type': 'done'})}\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'error': str(e)})}\n\n"

@app.get("/")
async def root():
    return {"status": "online", "g4f": G4F_AVAILABLE}

@app.get("/api/library/list")
@app.get("/library/list")
async def list_libraries():
    return JSONResponse(content={"libraries": []})

@app.get("/favicon.ico")
async def favicon():
    return Response(status_code=204)

@app.get("/api/ping")
async def ping():
    return JSONResponse(content={"ping": "pong"})

@app.post("/api/chatbot")
@app.post("/chatbot")
async def chatbot_proxy(request: Request):
    try:
        raw_body = await request.body()
        body = json.loads(raw_body.decode('utf-8')) if raw_body else {}
        user_input = body.get("input", "Hallo")
        history = body.get("history", [])
        
        return StreamingResponse(
            g4f_ai_stream(user_input, history),
            media_type="text/event-stream",
            headers={
                "X-Accel-Buffering": "no",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive"
            }
        )
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

# Vercel entry point
app = app
