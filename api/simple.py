import json
import httpx
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, JSONResponse

app = FastAPI()

@app.get("/health")
async def health():
    return {"status": "ok", "message": "Simple API working"}

@app.post("/api/chatbot")
async def chatbot(request: Request):
    try:
        data = await request.json()
        user_input = data.get("input", "")
        messages = data.get("messages", [])
        
        if not user_input and messages:
            user_input = messages[-1].get("content", "")
        
        # Direct Pollinations AI call - minimal implementation
        async def generate():
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(
                        "https://text.pollinations.ai/openai",
                        json={
                            "model": "openai",
                            "messages": [{"role": "user", "content": user_input}],
                            "stream": True
                        }
                    )
                    
                    if response.status_code == 200:
                        async for chunk in response.aiter_text():
                            if chunk.strip():
                                yield f"data: {json.dumps({'content': chunk})}\n\n"
                    else:
                        yield f"data: {json.dumps({'error': f'API Error: {response.status_code}'})}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'error': f'Service Error: {str(e)}'})}\n\n"
        
        return StreamingResponse(generate(), media_type="text/plain")
        
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"Server Error: {str(e)}"}
        )

# Vercel handler
def handler(request):
    return app(request.scope, receive, send)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
