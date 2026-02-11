import json
import httpx
import urllib.parse
import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
DEFAULT_MODEL = "openai"
MODELS = {
    "gpt-4o": "openai",
    "gpt-4o-mini": "openai",
    "mistral": "mistral",
    "llama": "llama",
    "search": "search",
    "claude-3-haiku": "openai", # Fallback to openai for haiku
    "deepseek": "deepseek",
    "flux": "flux" # Image model
}

# Specialized prompts
BUILDER_SYSTEM_PROMPT = """You are DUB5 AI, a world-class senior software architect developed by DUB55.
You are the core engine behind the DUB5 Web App Builder. 
When asked to build or modify an app/website, provide the full file structure.
Use this EXACT XML format for EVERY file:
<file path="filename.ext">
// Full file content here
</file>
1. Separate files: Use distinct <file> tags for HTML, CSS, JS, etc.
2. Completeness: Code must be 100% functional.
3. Image Generation: Use: ![Description](https://image.pollinations.ai/prompt/DESCRIPTION?width=1024&height=1024&nologo=true)."""

PERSONALITIES = {
    "general": "You are DUB5 AI, a helpful and professional assistant.",
    "coder": BUILDER_SYSTEM_PROMPT,
    "teacher": "You are DUB5 AI, a patient teacher. Explain concepts simply with analogies.",
    "writer": "You are DUB5 AI, a creative writer and storyteller."
}

THINKING_MODES = {
    "balanced": {"model": "openai", "system_add": ""},
    "concise": {"model": "openai", "system_add": " Be extremely concise."},
    "reason": {"model": "mistral", "system_add": " Use step-by-step reasoning."},
    "deep": {"model": "llama", "system_add": " Provide deep, detailed analysis."}
}

@app.post("/api/chatbot")
async def chatbot_simple(request: Request):
    try:
        body = await request.json()
        user_input = body.get("input", "")
        history = body.get("history", [])
        model_alias = body.get("model", "gpt-4o")
        mode = body.get("thinking_mode", "balanced")
        personality = body.get("personality", "general")
        
        # Base system prompt
        system_prompt = PERSONALITIES.get(personality, PERSONALITIES["general"])
        
        # Determine model
        if mode in THINKING_MODES:
            model = THINKING_MODES[mode]["model"]
            system_prompt += THINKING_MODES[mode]["system_add"]
        else:
            model = MODELS.get(model_alias, DEFAULT_MODEL)
        
        # Image capability
        if "![" not in system_prompt:
            system_prompt += " You can generate images with: ![Image](https://image.pollinations.ai/prompt/DESCRIPTION?width=1024&height=1024&nologo=true)."

        # Context construction
        full_prompt = ""
        context_msgs = history[-8:] if history else []
        for msg in context_msgs:
            role = "User" if msg["role"] == "user" else "Assistant"
            full_prompt += f"{role}: {msg['content']}\n"
        full_prompt += f"User: {user_input}\nAssistant:"

        async def generate():
            # Try multiple models/providers if one fails
            models_to_try = [model, "mistral", "llama", "openai"]
            # Remove duplicates while preserving order
            models_to_try = list(dict.fromkeys(models_to_try))
            
            last_error = None
            for attempt_model in models_to_try:
                try:
                    encoded_system = urllib.parse.quote(system_prompt)
                    encoded_prompt = urllib.parse.quote(full_prompt)
                    url = f"https://text.pollinations.ai/{encoded_prompt}?model={attempt_model}&system={encoded_system}&stream=true"
                    
                    async with httpx.AsyncClient(timeout=30.0) as client:
                        async with client.stream("GET", url) as response:
                            if response.status_code == 200:
                                sse_buffer = ""
                                async for chunk in response.aiter_text():
                                    if not chunk:
                                        continue
                                    sse_buffer += chunk
                                    events = sse_buffer.split("\n\n")
                                    sse_buffer = events.pop() if events else ""
                                    for evt in events:
                                        lines = [l.strip() for l in evt.split("\n") if l.strip()]
                                        payloads = []
                                        done_event = False
                                        for line in lines:
                                            if line.startswith("data:"):
                                                payload = line[5:].strip()
                                                if payload == "[DONE]":
                                                    done_event = True
                                                    continue
                                                if payload:
                                                    payloads.append(payload)
                                        for payload in payloads:
                                            content_text = ""
                                            reasoning_text = ""
                                            try:
                                                data = json.loads(payload)
                                                content_text = (
                                                    data.get("content")
                                                    or (data.get("delta") or {}).get("content")
                                                    or (
                                                        ((data.get("choices") or [{}])[0].get("delta") or {}).get("content")
                                                    )
                                                ) or ""
                                                reasoning_text = (
                                                    data.get("reasoning")
                                                    or data.get("reasoning_content")
                                                    or (data.get("delta") or {}).get("reasoning_content")
                                                    or (
                                                        ((data.get("choices") or [{}])[0].get("delta") or {}).get("reasoning_content")
                                                    )
                                                ) or ""
                                            except Exception:
                                                if not payload.startswith("{"):
                                                    content_text = payload
                                            if content_text:
                                                yield f"data: {json.dumps({'content': content_text})}\n\n"
                                            if reasoning_text:
                                                yield f"data: {json.dumps({'reasoning': reasoning_text})}\n\n"
                                        if done_event:
                                            yield "data: [DONE]\n\n"
                                            return
                                yield "data: [DONE]\n\n"
                                return
                            else:
                                last_error = f"HTTP {response.status_code}"
                                continue # Try next model
                except Exception as e:
                    last_error = str(e)
                    continue # Try next model
            
            # If all failed
            yield f"data: {json.dumps({'error': f'All providers failed. Last error: {last_error}'})}\n\n"

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
