import logging
import json
import httpx
import urllib.parse
import asyncio
import re
import time
import sys
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Track initialization start time
_init_start_time = time.time()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Log module initialization start
logger.info("=" * 60)
logger.info("Starting DUB5 Chatbot initialization")
logger.info(f"Python version: {sys.version}")
logger.info(f"Environment: {'Vercel' if 'VERCEL' in sys.modules else 'Local'}")

# Track module imports with timing
_module_load_times = {}

def _log_module_import(module_name: str, start_time: float):
    """Helper to log module import timing"""
    load_time = (time.time() - start_time) * 1000  # Convert to ms
    _module_load_times[module_name] = load_time
    logger.info(f"Loaded {module_name} in {load_time:.2f}ms")

# Import core modules with timing
_t = time.time()
from api.models import DEFAULT_MODEL, MODELS
_log_module_import("api.models", _t)

_t = time.time()
from api.thinking_modes import THINKING_MODES
_log_module_import("api.thinking_modes", _t)

_t = time.time()
from api.config import Config
_log_module_import("api.config", _t)

_t = time.time()
from api.chatbot_backup import stream_chat_completion
_log_module_import("api.chatbot_backup", _t)

_t = time.time()
from api.environment import Environment
_log_module_import("api.environment", _t)

_t = time.time()
from api.error_handler import (
    log_error,
    create_error_response,
    handle_ai_provider_error
)
_log_module_import("api.error_handler", _t)

# Detect environment and configure root path
root_path = Environment.get_root_path()
app = FastAPI(root_path=root_path)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Conditionally mount static files only when not running on Vercel
# In Vercel, static files are served through vercel.json routing configuration
if not Environment.is_vercel():
    logger.info("Local environment detected: mounting static files")
    app.mount("/static", StaticFiles(directory="public"), name="static")
else:
    logger.info("Vercel environment detected: static files will be served through Vercel routing")

# Log initialization completion with performance metrics
_init_end_time = time.time()
_total_init_time = (_init_end_time - _init_start_time) * 1000  # Convert to ms

logger.info("=" * 60)
logger.info("DUB5 Chatbot initialization complete")
logger.info(f"Total initialization time: {_total_init_time:.2f}ms")
logger.info(f"Loaded {len(_module_load_times)} modules:")
for module, load_time in _module_load_times.items():
    logger.info(f"  - {module}: {load_time:.2f}ms")
logger.info(f"Root path: {root_path}")
logger.info(f"Static files: {'mounted locally' if not Environment.is_vercel() else 'served via Vercel'}")
logger.info("=" * 60)

# Performance warning for cold starts
if _total_init_time > 10000:  # 10 seconds
    logger.warning(f"Cold start exceeded 10 seconds: {_total_init_time:.2f}ms")
elif _total_init_time > 5000:  # 5 seconds
    logger.info(f"Cold start time acceptable: {_total_init_time:.2f}ms")
else:
    logger.info(f"Cold start time optimal: {_total_init_time:.2f}ms")

@app.get("/")
async def get_chatbot_html():
    """
    Serves the main chatbot HTML interface.
    Reads directly from public/chatbot.html with proper error handling.
    """
    try:
        with open("public/chatbot.html", "r", encoding="utf-8") as f:
            content = f.read()
            return HTMLResponse(content=content)
    except FileNotFoundError as e:
        log_error(
            error_type="file",
            message="Chatbot HTML file not found at public/chatbot.html",
            exception=e,
            context={"file_path": "public/chatbot.html", "operation": "read"}
        )
        error_response = create_error_response(
            error_code="FILE_NOT_FOUND",
            message="Chatbot interface not found",
            details="The chatbot.html file is missing. Please check deployment."
        )
        return JSONResponse(content=error_response, status_code=404)
    except PermissionError as e:
        log_error(
            error_type="file",
            message="Permission denied reading chatbot.html",
            exception=e,
            context={"file_path": "public/chatbot.html", "operation": "read"}
        )
        error_response = create_error_response(
            error_code="PERMISSION_DENIED",
            message="Unable to access chatbot interface",
            details="Permission denied reading chatbot.html"
        )
        return JSONResponse(content=error_response, status_code=500)
    except UnicodeDecodeError as e:
        log_error(
            error_type="file",
            message="Encoding error reading chatbot.html",
            exception=e,
            context={"file_path": "public/chatbot.html", "operation": "read"}
        )
        error_response = create_error_response(
            error_code="ENCODING_ERROR",
            message="Unable to read chatbot interface",
            details="Encoding error reading chatbot.html"
        )
        return JSONResponse(content=error_response, status_code=500)
    except Exception as e:
        log_error(
            error_type="file",
            message="Unexpected error reading chatbot.html",
            exception=e,
            context={"file_path": "public/chatbot.html", "operation": "read"}
        )
        error_response = create_error_response(
            error_code="INTERNAL_ERROR",
            message="An unexpected error occurred",
            details="Unexpected error while loading the chatbot interface"
        )
        return JSONResponse(content=error_response, status_code=500)

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
    """
    Main chatbot endpoint that handles user messages and streams AI responses.
    Includes comprehensive error handling for all failure modes.
    """
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

    except json.JSONDecodeError as e:
        log_error(
            error_type="request",
            message="Invalid JSON in request body",
            exception=e,
            context={"endpoint": "/api/chatbot"}
        )
        error_response = create_error_response(
            error_code="INVALID_JSON",
            message="Invalid request format",
            details="Request body must be valid JSON"
        )
        return JSONResponse(content=error_response, status_code=400)
    
    except KeyError as e:
        log_error(
            error_type="request",
            message="Missing required field in request",
            exception=e,
            context={"endpoint": "/api/chatbot"}
        )
        error_response = create_error_response(
            error_code="MISSING_FIELD",
            message="Missing required field in request",
            details=f"Required field missing: {str(e)}"
        )
        return JSONResponse(content=error_response, status_code=400)
    
    except Exception as e:
        log_error(
            error_type="chatbot",
            message="Error in chatbot_response endpoint",
            exception=e,
            context={"endpoint": "/api/chatbot"}
        )
        error_response = create_error_response(
            error_code="INTERNAL_ERROR",
            message="An error occurred processing your request",
            details=str(e),
            retry_after=5
        )
        # Return as streaming response to match expected format
        async def error_stream():
            yield f"data: {json.dumps(error_response)}\n\n"
        
        return StreamingResponse(
            error_stream(),
            media_type="application/json"
        )

@app.get("/health")
async def health_check():
    """
    Health check endpoint that tests both AI backends.
    Always returns HTTP 200 with status details in response body.
    Includes 10-second timeout protection to prevent hanging.
    """
    async def check_backend(backend_name: str, force_roulette: bool, personality: str):
        """Helper function to check a single backend with timeout protection."""
        try:
            test_messages = [{"role": "user", "content": "Hello"}]
            test_response_generator = stream_chat_completion(
                messages=test_messages,
                model="gpt-4o",
                web_search=False,
                personality_name=personality,
                image_data=None,
                force_roulette=force_roulette,
                session_id=f"health_check_{backend_name}"
            )
            # Consume the generator to trigger the call and check for any content
            async for chunk in test_response_generator:
                if chunk.strip() and not chunk.startswith(":"): # Ignore heartbeats
                    data = json.loads(chunk.replace("data: ", ""))
                    if data.get("content"): # Check if any content is received
                        return {"status": "healthy", "error": None}
            return {"status": "unresponsive", "error": None}

        except asyncio.TimeoutError:
            return {"status": "unhealthy", "error": "Health check timeout"}
        except Exception as e:
            log_error(
                error_type="health_check",
                message=f"Health check failed for {backend_name}",
                exception=e,
                context={"provider": backend_name}
            )
            return {"status": "unhealthy", "error": str(e)}

    try:
        health_status = {
            "pollinations_ai": {"status": "unknown", "error": None},
            "g4f_ai": {"status": "unknown", "error": None}
        }

        # Test Pollinations AI path with 5-second timeout per backend
        try:
            health_status["pollinations_ai"] = await asyncio.wait_for(
                check_backend("pollinations_ai", False, "coder"),
                timeout=5.0
            )
        except asyncio.TimeoutError:
            health_status["pollinations_ai"] = {
                "status": "unhealthy",
                "error": "Health check timeout (5s)"
            }
        except Exception as e:
            log_error(
                error_type="health_check",
                message="Unexpected error checking Pollinations AI",
                exception=e,
                context={"provider": "pollinations_ai"}
            )
            health_status["pollinations_ai"] = {
                "status": "unhealthy",
                "error": str(e)
            }

        # Test g4f AI path with 5-second timeout per backend
        try:
            health_status["g4f_ai"] = await asyncio.wait_for(
                check_backend("g4f_ai", True, "general"),
                timeout=5.0
            )
        except asyncio.TimeoutError:
            health_status["g4f_ai"] = {
                "status": "unhealthy",
                "error": "Health check timeout (5s)"
            }
        except Exception as e:
            log_error(
                error_type="health_check",
                message="Unexpected error checking g4f AI",
                exception=e,
                context={"provider": "g4f_ai"}
            )
            health_status["g4f_ai"] = {
                "status": "unhealthy",
                "error": str(e)
            }
        
        # Always return 200 status with health details in body
        return JSONResponse(content=health_status, status_code=200)
    
    except Exception as e:
        # Even if the health check itself fails, return 200 with error details
        log_error(
            error_type="health_check",
            message="Unexpected error in health check endpoint",
            exception=e,
            context={"endpoint": "/health"}
        )
        error_response = {
            "pollinations_ai": {"status": "unknown", "error": "Health check failed"},
            "g4f_ai": {"status": "unknown", "error": "Health check failed"},
            "error": str(e)
        }
        return JSONResponse(content=error_response, status_code=200)
