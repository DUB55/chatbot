import logging
import json
import httpx
import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(root_path="")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files
app.mount("/static", StaticFiles(directory="public"), name="static")

# Root handler removed - let Vercel handle static files

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": "2025-02-18T15:35:00Z", "version": "1.0.0"}

@app.post("/api/chatbot")
async def chatbot_endpoint(request: Request):
    try:
        logger.info("Chatbot endpoint called")
        
        # Parse request
        data = await request.json()
        messages = data.get("messages", [])
        personality = data.get("personality", "general")
        model = data.get("model", "openai")
        
        # Create system message based on personality
        if personality == "coder":
            system_message = """You are DUB5, an AI editor that creates and modifies web applications. 
            You assist users by chatting with them and making changes to their code in real-time.
            Generate complete, standalone HTML, CSS, and JavaScript files.
            Always provide full code with proper structure."""
        else:
            system_message = "You are a helpful AI assistant."
        
        # Add system message to conversation
        full_messages = [{"role": "system", "content": system_message}] + messages
        
        # Call Pollinations AI directly (simplified for Vercel)
        pollinations_url = "https://text.pollinations.ai/openai"
        pollinations_payload = {
            "messages": full_messages,
            "model": "openai",
            "stream": True
        }
        
        async def generate_response():
            async with httpx.AsyncClient(timeout=60.0) as client:
                async with client.stream("POST", pollinations_url, json=pollinations_payload) as response:
                    if response.is_success:
                        yield f"data: {json.dumps({'type': 'metadata', 'model': model, 'personality': personality})}\n\n"
                        yield ": heartbeat\n\n"
                        
                        buffer = b""
                        async for chunk in response.aiter_bytes():
                            buffer += chunk
                            while b"\n" in buffer:
                                line, buffer = buffer.split(b"\n", 1)
                                line = line.decode("utf-8").strip()
                                if line.startswith("data: "):
                                    data_str = line[6:]
                                    if data_str == "[DONE]":
                                        break
                                    try:
                                        chunk_data = json.loads(data_str)
                                        content = chunk_data.get("choices", [{}])[0].get("delta", {}).get("content", "")
                                        if content:
                                            yield f"data: {json.dumps({'type': 'chunk', 'content': content})}\n\n"
                                    except json.JSONDecodeError:
                                        continue
                        yield f"data: {json.dumps({'type': 'end', 'content': 'Stream finished'})}\n\n"
                    else:
                        error_text = await response.aread()
                        logger.error(f"Pollinations error: {response.status_code} - {error_text.decode()}")
                        yield f"data: {json.dumps({'type': 'error', 'content': f'AI service error: {response.status_code}'})}\n\n"
        
        return StreamingResponse(generate_response(), media_type="text/plain")
        
    except Exception as e:
        logger.error(f"Chatbot endpoint error: {e}")
        return StreamingResponse(
            iter([f"data: {json.dumps({'type': 'error', 'content': f'Server error: {str(e)}'})}\n\n"]),
            media_type="text/plain"
        )

# Test endpoint (already working)
@app.post("/api/test")
async def test_endpoint(request: Request):
    try:
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "status": "success",
                "message": "Vercel Python function is working",
                "method": request.method,
                "url": str(request.url)
            })
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "status": "error", 
                "message": str(e)
            })
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
