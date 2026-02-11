import json
import httpx
import urllib.parse
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/api/chatbot")
async def chatbot_simple(request: Request):
    try:
        # Get request body
        body = await request.json()
        user_input = body.get("input", "Hallo")
        
        # Simple Pollinations request (no streaming)
        encoded_query = urllib.parse.quote(user_input)
        url = f"https://text.pollinations.ai/{encoded_query}?model=openai&system=You%20are%20DUB5%20AI"
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url)
            if response.status_code == 200:
                return JSONResponse(content={"response": response.text})
            else:
                return JSONResponse(content={"error": f"HTTP {response.status_code}"}, status_code=500)
                
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

@app.get("/api/debug")
async def debug_info():
    return {"status": "simple_mode"}

@app.get("/api/status")
@app.get("/status")
def status():
    return {"status": "ok", "message": "Ultra-lightweight status check working"}