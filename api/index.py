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

# Configureer logging voor debugging
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

async def pollinations_ai_stream(user_query: str, history: list) -> AsyncGenerator[str, None]:
    """Pollinations AI - Altijd werkend, geen dependencies."""
    try:
        logger.info(f"--- DEBUG: Pollinations AI Start ---")
        logger.info(f"DEBUG: User query: {user_query[:100]}")
        
        # Bouw de URL met de juiste parameters
        encoded_query = urllib.parse.quote(user_query)
        url = f"https://text.pollinations.ai/{encoded_query}?model=openai&system=You%20are%20DUB5%20AI%2C%20a%20helpful%20assistant.%20Answer%20in%20Dutch."
        
        logger.info(f"DEBUG: Pollinations URL: {url}")
        
        # Start meteen met SSE streaming
        yield f"data: {json.dumps({'type': 'start', 'source': 'pollinations'})}\n\n"
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            async with client.stream("GET", url) as response:
                logger.info(f"DEBUG: Pollinations response status: {response.status_code}")
                
                if response.status_code == 200:
                    yield f"data: {json.dumps({'type': 'metadata', 'model': 'pollinations'})}\n\n"
                    
                    # Stream de response in chunks
                    total_chars = 0
                    async for chunk in response.aiter_text():
                        if chunk:
                            chunk_len = len(chunk)
                            total_chars += chunk_len
                            logger.info(f"DEBUG: Received chunk of {chunk_len} chars (total: {total_chars})")
                            yield f"data: {json.dumps({'content': chunk})}\n\n"
                    
                    logger.info(f"DEBUG: Streaming completed, total chars: {total_chars}")
                    yield f"data: {json.dumps({'type': 'done'})}\n\n"
                else:
                    error_msg = f"Pollinations HTTP error: {response.status_code}"
                    logger.error(f"DEBUG: {error_msg}")
                    yield f"data: {json.dumps({'error': error_msg})}\n\n"
                    
    except Exception as e:
        error_msg = f"Pollinations Fatal Error: {str(e)}"
        logger.error(f"DEBUG: {error_msg}")
        yield f"data: {json.dumps({'error': error_msg})}\n\n"

@app.get("/api/debug")
async def debug_info():
    """Geeft systeem informatie voor debugging op Vercel."""
    return {
        "python_version": sys.version,
        "cwd": os.getcwd(),
        "env_vars": {k: "SET" for k in os.environ.keys() if "KEY" not in k.upper() and "TOKEN" not in k.upper()},
        "backend_type": "pollinations_only",
        "tmp_writable": os.access('/tmp', os.W_OK) if os.path.exists('/tmp') else False
    }

@app.get("/")
async def root():
    return {"status": "online", "backend": "pollinations_ai", "version": "1.3.0"}

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
        # Parse request body
        raw_body = await request.body()
        logger.info(f"DEBUG: Raw body length: {len(raw_body)}")
        
        try:
            body = json.loads(raw_body.decode('utf-8')) if raw_body else {}
            logger.info(f"DEBUG: Parsed body: {json.dumps(body)[:200]}...")
        except Exception as e:
            logger.error(f"DEBUG: JSON parse error: {e}")
            body = {}
        
        user_input = body.get("input", "Hallo")
        history = body.get("history", [])
        
        logger.info(f"DEBUG: User input: '{user_input[:50]}' (length: {len(user_input)})")
        logger.info(f"DEBUG: History length: {len(history)}")
        
        return StreamingResponse(
            pollinations_ai_stream(user_input, history),
            media_type="text/event-stream",
            headers={
                "X-Accel-Buffering": "no",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Debug-Backend": "pollinations"
            }
        )
        
    except Exception as e:
        logger.error(f"DEBUG: Fatal error in chatbot_proxy: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "error": "Backend Fatal Crash",
                "detail": str(e),
                "debug_info": "Check server logs for stacktrace"
            }
        )

# Vercel entry point - gebruik de bestaande app