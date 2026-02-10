import json
import logging
import httpx
import asyncio
from typing import AsyncGenerator

# Minimale logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def fallback_pollinations_ai(messages: list) -> AsyncGenerator[str, None]:
    """Ultra-lichte fallback die GEEN lokale bestanden nodig heeft."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
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
                    yield f"data: {json.dumps({'error': f'AI Provider Error: {response.status_code}'})}\n\n"
                    return
                
                yield f"data: {json.dumps({'type': 'metadata', 'model': 'pollinations-fallback'})}\n\n"
                
                async for line in response.aiter_lines():
                    if not line.strip(): continue
                    clean_line = line.strip()
                    if clean_line.startswith("data: "): clean_line = clean_line[6:]
                    if clean_line == "[DONE]": break
                    
                    try:
                        if clean_line.startswith('{'):
                            chunk_data = json.loads(clean_line)
                            content = chunk_data.get("choices", [{}])[0].get("delta", {}).get("content", "")
                            if content: yield f"data: {json.dumps({'content': content})}\n\n"
                        else:
                            yield f"data: {json.dumps({'content': clean_line})}\n\n"
                    except:
                        yield f"data: {json.dumps({'content': clean_line})}\n\n"
                
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'error': str(e)})}\n\n"

# FastAPI blijft als wrapper voor lokaal gebruik, maar we maken de route NOG simpeler
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/system-status")
@app.get("/status")
async def status():
    return {"status": "ok", "mode": "ultra-light"}

@app.post("/api/chatbot")
@app.post("/chatbot")
async def chatbot_proxy(request: Request):
    try:
        body = await request.json()
    except:
        body = {"input": "Hello", "history": []}
    
    user_input = body.get("input", "Hello")
    history = body.get("history", [])
    messages = [{"role": "system", "content": "You are DUB5 AI."}]
    for m in history:
        if isinstance(m, dict) and "role" in m:
            messages.append({"role": m["role"], "content": m.get("content", "")})
    messages.append({"role": "user", "content": user_input})

    return StreamingResponse(
        fallback_pollinations_ai(messages),
        media_type="text/event-stream",
        headers={
            "X-Accel-Buffering": "no",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive"
        }
    )

# Voor Vercel is 'app' de export die hij zoekt
