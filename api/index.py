import json
import httpx
import urllib.parse
import sys
import os
from typing import AsyncGenerator
from fastapi import FastAPI, Request, Response
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

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
        # Bouw de URL met de juiste parameters
        encoded_query = urllib.parse.quote(user_query)
        url = f"https://text.pollinations.ai/{encoded_query}?model=openai&system=You%20are%20DUB5%20AI%2C%20a%20helpful%20assistant.%20Answer%20in%20Dutch."
        
        # Start meteen met SSE streaming
        yield f"data: {json.dumps({'type': 'start', 'source': 'pollinations'})}\n\n"
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            async with client.stream("GET", url) as response:
                if response.status_code == 200:
                    yield f"data: {json.dumps({'type': 'metadata', 'model': 'pollinations'})}\n\n"
                    
                    # Stream de response in chunks
                    async for chunk in response.aiter_text():
                        if chunk:
                            yield f"data: {json.dumps({'content': chunk})}\n\n"
                    
                    yield f"data: {json.dumps({'type': 'done'})}\n\n"
                else:
                    error_msg = f"Pollinations HTTP error: {response.status_code}"
                    yield f"data: {json.dumps({'error': error_msg})}\n\n"
                    
    except Exception as e:
        error_msg = f"Pollinations Fatal Error: {str(e)}"
        yield f"data: {json.dumps({'error': error_msg})}\n\n"

@app.get("/api/debug")
async def debug_info():
    """Geeft systeem informatie voor debugging op Vercel."""
    return {
        "python_version": sys.version,
        "cwd": os.getcwd(),
        "backend_type": "pollinations_only_minimal",
        "status": "online"
    }

@app.get("/")
async def root():
    return {"status": "online", "backend": "pollinations_ai", "version": "1.3.1_minimal"}

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
        # Parse request body
        raw_body = await request.body()
        body = json.loads(raw_body.decode('utf-8')) if raw_body else {}
        user_input = body.get("input", "Hallo")
        history = body.get("history", [])
        
        return StreamingResponse(
            pollinations_ai_stream(user_input, history),
            media_type="text/event-stream",
            headers={
                "X-Accel-Buffering": "no",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive"
            }
        )
        
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "error": "Backend Error", 
                "detail": str(e)
            }
        )