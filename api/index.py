import logging
import json
import httpx
import urllib.parse
import asyncio
import re
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from api.chatbot_backup import stream_chat_completion
from api.models import DEFAULT_MODEL, MODELS
from api.thinking_modes import THINKING_MODES

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files (CSS, JS, etc.)
app.mount("/static", StaticFiles(directory="."), name="static")

@app.get("/")
async def get_chatbot_html():
    with open("chatbot.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

# Configuration


# Specialized prompts
BUILDER_SYSTEM_PROMPT = """You are DUB5, an AI editor that creates and modifies web applications. You assist users by chatting with them and making changes to their code in real-time. You can add images to the project using pollinations ai image url generating functionality, and you can use them in your responses.

Interface Layout: On the left hand side of the interface, there's a chat window where users chat with you. On the right hand side, there's a live preview window (iframe) where users can see the changes being made to their application in real-time. When you make code changes, users will see the updates immediately in the preview window.

Technology Stack: All DUB5 projects are currently built using standalone HTML, CSS, and JavaScript. You should prioritize generating these types of files. It is not possible for DUB5 to support other frameworks like React, Angular, Vue, Svelte, Next.js, native mobile apps, etc.

Backend Limitations: DUB5 cannot run backend code directly. It cannot run Python, Node.js, Ruby, etc.

## Code Generation Guidelines

- **CRITICAL: ALWAYS output code as file directives, NOT chat code fences.**
- **For EACH file, you MUST emit this structure with NO extra prose before/after:**
BEGIN_FILE: <relative-path-from-project-root>
<full file content>
END_FILE

- Path hints: always include a valid, relative path with an appropriate extension.
  Use html→.html, css→.css, js→.js, json→.json, md→.md.
  Place assets in sensible locations: pages at project root or /pages, components under /components, styles under /styles.
- No chat code: do not print code fences in chat. Narrative must be Markdown without code blocks; keep it short and focused.
- Multi-file outputs: emit multiple file blocks back-to-back with BEGIN_FILE/END_FILE per file. Include all files needed (HTML, CSS, JS) in separate blocks.
- Determinism: be explicit about filenames and directories; never rely on the app to guess.
  If editing an existing file, emit the same BEGIN_FILE path and the full updated content.
- Error handling: if a file path is ambiguous, first output a short Markdown bullet list stating required files and their exact paths, then emit the file blocks.
- If the user says "Continue EXACTLY where you left off/stopped", you MUST continue your previous response IMMEDIATELY from the last character, without any introductory text, conversational filler, preambles, or explanations. DO NOT add anything before resuming the content.

## Design Principles

- ALWAYS generate beautiful and responsive designs using standard HTML and CSS.
- Prioritize semantic HTML for accessibility and maintainability.
- Use clean, well-structured CSS for styling. Organize CSS logically (e.g., using external stylesheets, BEM methodology, or similar).
- Ensure designs are responsive and adapt well to various screen sizes and devices.
- Pay attention to contrast, color, and typography to create visually appealing interfaces.
- Avoid inline styles; prefer external CSS files or `<style>` blocks within HTML for component-specific styles.
- When generating CSS, consider using CSS variables for theming and easy customization.
"""

PERSONALITIES = {
    "general": "You are DUB5 AI, a helpful and professional assistant.",
    "coder": BUILDER_SYSTEM_PROMPT,
    "teacher": "You are DUB5 AI, a patient teacher. Explain concepts simply with analogies.",
    "writer": "You are DUB5 AI, a creative writer and storyteller."
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
async def chatbot_response(request: Request):
    try:
        body = await request.json()
        user_input = body.get("input", "")
        history = body.get("history", [])
        model_alias = body.get("model", "gpt-4o")
        mode = body.get("thinking_mode", "balanced")
        personality = body.get("personality", "general")
        custom_system_prompt = body.get("custom_system_prompt")
        force_roulette = body.get("force_roulette", False)
        files = body.get("files", [])
        image_data = body.get("image")
        session_id = body.get("session_id", "default")
        library_ids = body.get("library_ids", [])

        # Base system prompt
        system_prompt = PERSONALITIES.get(personality, PERSONALITIES["general"])

        # Determine model
        if mode in THINKING_MODES:
            model = THINKING_MODES[mode]["model"]
            system_prompt += THINKING_MODES[mode]["system_add"]
        else:
            model = MODELS.get(model_alias, DEFAULT_MODEL)

        # If custom_system_prompt is provided, it overrides the personality prompt
        if custom_system_prompt:
            system_prompt = custom_system_prompt

        # Image capability
        if "![" not in system_prompt:
            system_prompt += " You can generate images with: ![Image](https://image.pollinations.ai/prompt/DESCRIPTION?width=1024&height=1024&nologo=true)."

        # Construct messages for the AI
        messages = [{"role": "system", "content": system_prompt}]
        for msg in history:
            messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": user_input})

        # Call the stream_chat_completion function
        return StreamingResponse(
            stream_chat_completion(
                messages=messages,
                model=model,
                web_search=False, # Assuming web_search is not directly controlled by this endpoint yet
                personality_name=personality,
                image_data=image_data,
                force_roulette=force_roulette,
                session_id=session_id
            ),
            media_type="application/json"
        )

    except Exception as e:
        logger.error(f"Error in chatbot_response: {e}", exc_info=True)
        return StreamingResponse(
            content=iter([json.dumps({"error": str(e)}) + "\n\n"]),
            media_type="application/json"
        )
