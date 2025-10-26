import os
import json
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
import asyncio

# ---- Import your AI client ----
from g4f.client import Client

# ---- Load system prompt from environment variable ----
SYSTEM_PROMPT = os.environ.get(
    "DUB5_SYSTEM_PROMPT",
    """
    You are DUB5, an AI assistant created by DUB55.
    IMPORTANT: Always identify yourself as DUB5, never as ChatGPT or any other AI.
    (Add your traits and behavior rules here)
    """
)

app = FastAPI()
client = Client()

# ---- Configure CORS ----
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],         # You can restrict to frontend URL(s)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- Request body schema ----
class UserInput(BaseModel):
    input: str

# ---- Chat streaming helper ----
async def stream_chat_completion(messages):
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=messages,
            web_search=False,
            stream=True,
            timeout=30
        )
        for chunk in response:
            if hasattr(chunk.choices[0], 'delta') and hasattr(chunk.choices[0].delta, 'content'):
                content = chunk.choices[0].delta.content
                if content:
                    yield f"data: {json.dumps({'content': content})}\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'error': str(e)})}\n\n"

# ---- Main chat API endpoint ----
@app.post("/api/chatbot")
async def chatbot_response(user_input: UserInput):
    try:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_input.input}
        ]
        return StreamingResponse(
            stream_chat_completion(messages),
            media_type='text/event-stream'
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ---- Optional chat history endpoint ----
chat_history = []

@app.get("/api/chat-history")
async def get_chat_history():
    return {
        "history": [msg for msg in chat_history if msg.get("role") != "system"]
    }

# ---- (Optional) Health check endpoint ----
@app.get("/")
async def health_check():
    return {"status": "ok"}

# ---- Run with Uvicorn if standalone ----
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
