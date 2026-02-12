import json
import httpx
import urllib.parse
import asyncio
import re
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
You power the DUB5 Web App Builder.

Rules:
- **CRITICAL: ALWAYS output code as file directives, NOT chat code fences.**
- **For EACH file, you MUST emit this structure with NO extra prose before/after:**
BEGIN_FILE: <relative-path-from-project-root>
<full file content>
END_FILE

- Path hints: always include a valid, relative path with an appropriate extension.
  Use html→.html, css→.css, js→.js, ts→.ts, tsx→.tsx, json→.json, md→.md.
  Place assets in sensible locations: pages at project root or /pages, components under /components, styles under /styles.
- No chat code: do not print code fences in chat. Narrative must be Markdown without code blocks; keep it short and focused.
- Multi-file outputs: emit multiple file blocks back-to-back with BEGIN_FILE/END_FILE per file. Include all files needed (HTML, CSS, JS) in separate blocks.
- Determinism: be explicit about filenames and directories; never rely on the app to guess.
  If editing an existing file, emit the same BEGIN_FILE path and the full updated content.
- Error handling: if a file path is ambiguous, first output a short Markdown bullet list stating required files and their exact paths, then emit the file blocks.
- If the user says "Continue EXACTLY where you left off/stopped", you MUST continue your previous response IMMEDIATELY from the last character, without any introductory text, conversational filler, preambles, or explanations. DO NOT add anything before resuming the content.

Images: When an image is required, include a link using:
![Description](https://image.pollinations.ai/prompt/DESCRIPTION?width=1024&height=1024&nologo=true)."""

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

async def ddg_search(query: str):
    url = f"https://api.duckduckgo.com/?q={urllib.parse.quote(query)}&format=json&no_redirect=1&no_html=1"
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.get(url)
        if r.status_code != 200:
            return []
        data = r.json()
    items = []
    for item in data.get("RelatedTopics", []):
        if isinstance(item, dict):
            t = item.get("Text") or item.get("Name") or ""
            u = item.get("FirstURL") or ""
            if t and u:
                items.append({"title": t, "url": u})
    for item in data.get("Results", []):
        if isinstance(item, dict):
            t = item.get("Text") or ""
            u = item.get("FirstURL") or ""
            if t and u:
                items.append({"title": t, "url": u})
    return items[:5]

async def fetch_readable(url: str):
    u = url.strip()
    if u.startswith("http://"):
        wrapped = "https://r.jina.ai/http://" + u[len("http://"):]
    elif u.startswith("https://"):
        wrapped = "https://r.jina.ai/http://" + u[len("https://"):]
    else:
        wrapped = "https://r.jina.ai/http://" + u
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.get(wrapped)
        if r.status_code != 200:
            return ""
        txt = r.text
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt[:3000]

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
        base_input = user_input.split("[Instruction:")[0].strip()
        if context_msgs:
            last = context_msgs[-1]
            if last.get("role") == "user" and (last.get("content","").strip() == base_input or last.get("content","").strip() == user_input.strip()):
                context_msgs = context_msgs[:-1]
        for msg in context_msgs:
            role = "User" if msg["role"] == "user" else "Assistant"
            full_prompt += f"{role}: {msg['content']}\n"
        full_prompt += f"User: {user_input}\nAssistant:"

        async def generate_browse():
            try:
                yield f"data: {json.dumps({'content': 'Searching web...'})}\n\n"
                sources = await ddg_search(user_input)
                if not sources:
                    yield f"data: {json.dumps({'content': 'No sources found.'})}\n\n"
                    yield "data: [DONE]\n\n"
                    return
                titles = [s.get('title', '') for s in sources]
                yield f"data: {json.dumps({'content': 'Found sources: ' + ', '.join([f'[{i+1}] {t}' for i,t in enumerate(titles)])})}\n\n"
                fetched = []
                for s in sources[:3]:
                    txt = await fetch_readable(s.get('url', ''))
                    if txt:
                        fetched.append({"title": s.get("title",""), "url": s.get("url",""), "text": txt})
                src_block = ""
                for i, s in enumerate(fetched):
                    src_block += f"[{i+1}] {s['title']} ({s['url']})\n{ s['text'] }\n\n"
                browse_prompt = f"Sources:\n{src_block}\nUser: {user_input}\nAssistant:"
                encoded_system = urllib.parse.quote(system_prompt + " Use only the sources and cite as [1], [2].")
                encoded_prompt = urllib.parse.quote(browse_prompt)
                url = f"https://text.pollinations.ai/{encoded_prompt}?model=openai&system={encoded_system}&stream=true"
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
                                    for line in lines:
                                        if line.startswith("data:"):
                                            payload = line[5:].strip()
                                            if payload == "[DONE]":
                                                yield "data: [DONE]\n\n"
                                                return
                                            if not payload:
                                                continue
                                            try:
                                                data = json.loads(payload)
                                                content_text = (
                                                    data.get("content")
                                                    or (data.get("delta") or {}).get("content")
                                                    or (((data.get("choices") or [{}])[0].get("delta") or {}).get("content"))
                                                ) or ""
                                                reasoning_text = (
                                                    data.get("reasoning")
                                                    or data.get("reasoning_content")
                                                    or (data.get("delta") or {}).get("reasoning_content")
                                                    or (((data.get("choices") or [{}])[0].get("delta") or {}).get("reasoning_content"))
                                                ) or ""
                                            except Exception:
                                                content_text = "" 
                                                reasoning_text = ""
                                            if content_text:
                                                yield f"data: {json.dumps({'content': content_text})}\n\n"
                                            if reasoning_text:
                                                yield f"data: {json.dumps({'reasoning': reasoning_text})}\n\n"
                            yield "data: [DONE]\n\n"
                            return
                        else:
                            yield f"data: {json.dumps({'error': 'Browse generation failed'})}\n\n"
                            yield "data: [DONE]\n\n"
                            return
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
                yield "data: [DONE]\n\n"
                return

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

        if model_alias == "search":
            return StreamingResponse(generate_browse(), media_type="text/event-stream")
        else:
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
