from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, JSONResponse
import json
import httpx
import traceback
import sys
import os
import time
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

@app.get("/health")
async def health_check():
    return {
        "status": "healthy", 
        "timestamp": time.time(), 
        "version": "1.0.0",
        "python_version": sys.version,
        "environment": "vercel"
    }

@app.get("/debug")
async def debug_info():
    return {
        "python_version": sys.version,
        "environment": {
            "vercel": os.environ.get("VERCEL", "not_set"),
            "region": os.environ.get("VERCEL_REGION", "not_set"),
            "env": os.environ.get("VERCEL_ENV", "not_set")
        },
        "working_directory": os.getcwd(),
        "imports_successful": True
    }

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
            try:
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
            except Exception as e:
                logger.error(f"Streaming error: {e}")
                yield f"data: {json.dumps({'type': 'error', 'content': f'Streaming error: {str(e)}'})}\n\n"
        
        return StreamingResponse(generate_response(), media_type="text/plain")
        
    except Exception as e:
        error_details = {
            "error": str(e),
            "traceback": traceback.format_exc(),
            "python_version": sys.version,
            "request_method": request.method,
            "request_url": str(request.url),
            "timestamp": time.time()
        }
        logger.error(f"Chatbot error: {error_details}")
        
        return JSONResponse(
            status_code=500,
            content={
                "type": "error",
                "content": f'Server error: {str(e)}',
                "details": error_details
            }
        )

# Vercel serverless function handler
def handler(request):
    return app(request.scope, receive, send)

# For local testing
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
