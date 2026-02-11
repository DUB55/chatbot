import json
import httpx
import urllib.parse
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
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
        
        # Simple Pollinations request
        encoded_query = urllib.parse.quote(user_input)
        url = f"https://text.pollinations.ai/{encoded_query}?model=openai&system=You%20are%20DUB5%20AI"
        
        async def generate():
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url)
                if response.status_code == 200:
                    # Send in the format frontend expects
                    data = json.dumps({"content": response.text})
                    yield f"data: {data}\n\n"
                    yield "data: [DONE]\n\n"
                else:
                    error_data = json.dumps({"error": f"HTTP {response.status_code}"})
                    yield f"data: {error_data}\n\n"

        return StreamingResponse(generate(), media_type="text/event-stream")
                
    except Exception as e:
        async def error_gen():
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        return StreamingResponse(error_gen(), media_type="text/event-stream")

@app.get("/api/debug")
async def debug_info():
    return {"status": "simple_mode"}

@app.get("/api/status")
@app.get("/status")
def status():
    return {"status": "ok", "message": "Ultra-lightweight status check working"}