import json
import logging
import httpx
import asyncio
import urllib.parse
from typing import AsyncGenerator
from fastapi import FastAPI, Request, Response
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

# Minimale logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

async def fallback_pollinations_ai(messages: list) -> AsyncGenerator[str, None]:
    """Directe verbinding met Pollinations AI."""
    try:
        # We maken het NOG simpeler voor Pollinations
        system_prompt = "You are DUB5 AI, a helpful assistant."
        user_query = messages[-1]["content"] if messages else "Hello"
        
        # Gebruik urllib.parse.quote in plaats van het niet-bestaande httpx.utils.quote
        encoded_query = urllib.parse.quote(user_query)
        encoded_system = urllib.parse.quote(system_prompt)
        url = f"https://text.pollinations.ai/{encoded_query}?model=openai&system={encoded_system}"
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream("GET", url) as response:
                if response.status_code != 200:
                    yield f"data: {json.dumps({'error': f'AI Provider Error: {response.status_code}'})}\n\n"
                    return
                
                yield f"data: {json.dumps({'type': 'metadata', 'model': 'pollinations'})}\n\n"
                
                async for chunk in response.aiter_text():
                    if chunk:
                        # Stuur de tekst direct door als content
                        yield f"data: {json.dumps({'content': chunk})}\n\n"
                
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
    except Exception as e:
        logger.error(f"Pollinations Stream Error: {e}")
        yield f"data: {json.dumps({'error': str(e)})}\n\n"

@app.get("/")
async def root():
    return {"message": "DUB5 AI API is running"}

@app.get("/api/system-status")
@app.get("/status")
@app.get("/system-status")
async def status():
    return {"status": "ok", "mode": "ultra-light"}

@app.get("/api/library/list")
async def list_libraries():
    return {"libraries": []}

@app.get("/favicon.ico")
async def favicon():
    return Response(status_code=204)

@app.post("/api/chatbot")
@app.post("/chatbot")
async def chatbot_proxy(request: Request):
    logger.info("Chatbot Proxy POST request started")
    body = {"input": "Hello", "history": []}
    
    try:
        raw_body = await request.body()
        if raw_body:
            try:
                body = json.loads(raw_body.decode('utf-8'))
            except Exception as parse_err:
                logger.error(f"Manual JSON Parse Error: {parse_err}")
        
        user_input = body.get("input", "Hello")
        history = body.get("history", [])
        
        messages = [{"role": "system", "content": "You are DUB5 AI."}]
        if isinstance(history, list):
            for m in history:
                if isinstance(m, dict) and "role" in m:
                    messages.append({"role": m["role"], "content": m.get("content", "")})
        
        messages.append({"role": "user", "content": str(user_input)})

        logger.info(f"Preparing StreamingResponse for input: {user_input[:50]}...")
        
        return StreamingResponse(
            fallback_pollinations_ai(messages),
            media_type="text/event-stream",
            headers={
                "X-Accel-Buffering": "no",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive"
            }
        )
    except Exception as e:
        logger.error(f"Chatbot Proxy Fatal Error: {e}")
        return JSONResponse(
            status_code=500, 
            content={"error": f"Fatal Proxy Error: {str(e)}", "type": "proxy_crash"}
        )

# Voor Vercel is 'app' de export die hij zoekt
