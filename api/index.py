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

# G4F Import (Lazy & Minimal)
def get_g4f():
    try:
        import g4f
        # Forceer g4f om /tmp te gebruiken voor cache op Vercel
        os.environ['G4F_CACHE_DIR'] = '/tmp/.g4f_cache'
        return g4f
    except Exception as e:
        logger.error(f"Lazy G4F Import Error: {e}")
        return None

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
    """Herstelde G4F AI functionaliteit (Lichtgewicht & Veilig)."""
    try:
        g4f_lib = get_g4f()
        if not g4f_lib:
            logger.warning("G4F not available, skipping to fallback.")
            async for chunk in simple_pollinations_stream(user_query):
                yield chunk
            return

        messages = [{"role": "system", "content": "You are DUB5 AI, a helpful assistant. Answer in Dutch."}]
        for m in history[-5:]: 
            if isinstance(m, dict) and "role" in m:
                messages.append({"role": m["role"], "content": m.get("content", "")})
        
        messages.append({"role": "user", "content": user_query})

        # Gebruik een stabiele provider die GEEN extra dependencies nodig heeft
        provider = g4f_lib.Provider.Blackbox 

        logger.info(f"Connecting to G4F (Provider: {provider.__name__})...")
        yield f"data: {json.dumps({'type': 'metadata', 'model': 'g4f-minimal'})}\n\n"

        # G4F Async Iterator met timeout
        try:
            response = await g4f_lib.ChatCompletion.create_async(
                model=g4f_lib.models.default,
                messages=messages,
                provider=provider,
                stream=True
            )

            async for chunk in response:
                if chunk:
                    yield f"data: {json.dumps({'content': chunk})}\n\n"
            
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            logger.info("G4F Stream completed")
        except Exception as inner_e:
            logger.error(f"G4F Stream inner error: {inner_e}")
            raise inner_e

    except Exception as e:
        logger.error(f"G4F Global Error: {e}")
        logger.info("Falling back to Pollinations due to error...")
        async for chunk in simple_pollinations_stream(user_query):
            yield chunk

async def simple_pollinations_stream(user_query: str) -> AsyncGenerator[str, None]:
    """Stabiele Pollinations Fallback (Gegarandeerd antwoord)."""
    try:
        encoded_query = urllib.parse.quote(user_query)
        # Gebruik de simpele GET interface die altijd werkt
        url = f"https://text.pollinations.ai/{encoded_query}?model=openai&system=You%20are%20DUB5%20AI"
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            async with client.stream("GET", url) as response:
                if response.status_code == 200:
                    yield f"data: {json.dumps({'type': 'metadata', 'model': 'pollinations-fallback'})}\n\n"
                    async for chunk in response.aiter_text():
                        if chunk: yield f"data: {json.dumps({'content': chunk})}\n\n"
                    yield f"data: {json.dumps({'type': 'done'})}\n\n"
                else:
                    yield f"data: {json.dumps({'error': f'AI Fallback Error: {response.status_code}'})}\n\n"
    except Exception as e:
        logger.error(f"Pollinations Fallback Fatal: {e}")
        yield f"data: {json.dumps({'error': str(e)})}\n\n"

@app.get("/api/debug")
async def debug_info():
    """Geeft systeem informatie voor debugging op Vercel."""
    return {
        "python_version": sys.version,
        "cwd": os.getcwd(),
        "env_vars": {k: "SET" for k in os.environ.keys() if "KEY" not in k.upper() and "TOKEN" not in k.upper()},
        "g4f_available": get_g4f() is not None,
        "tmp_writable": os.access('/tmp', os.W_OK) if os.path.exists('/tmp') else False
    }

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
    logger.info("--- DEBUG: Backend Chatbot Request Started ---")
    try:
        # Log headers
        headers = dict(request.headers)
        logger.info(f"DEBUG: Headers: {json.dumps(headers)}")

        raw_body = await request.body()
        logger.info(f"DEBUG: Raw Body Length: {len(raw_body)}")
        
        try:
            body = json.loads(raw_body.decode('utf-8')) if raw_body else {}
            logger.info(f"DEBUG: Body Parsed: {json.dumps(body)[:200]}...")
        except Exception as e:
            logger.error(f"DEBUG: JSON Parse Error: {e}")
            body = {}

        user_input = body.get("input", "Hallo")
        history = body.get("history", [])
        
        logger.info(f"DEBUG: Selected input: {user_input[:50]}")
        
        return StreamingResponse(
            g4f_ai_stream(user_input, history),
            media_type="text/event-stream",
            headers={
                "X-Accel-Buffering": "no",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Debug-Status": "streaming-started"
            }
        )
    except Exception as e:
        logger.error(f"DEBUG: Fatal Chatbot Proxy Error: {e}", exc_info=True)
        return JSONResponse(
            status_code=500, 
            content={
                "error": "Backend Fatal Crash", 
                "detail": str(e),
                "debug_info": "Check server logs for stacktrace"
            }
        )

# Vercel entry point
app = app
