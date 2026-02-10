import os
import json
import sys
import httpx
import random
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional, List, Dict, Any, AsyncGenerator

# Voeg de huidige map toe aan sys.path voor imports
current_dir = Path(__file__).parent.absolute()
if str(current_dir) not in sys.path:
    sys.path.append(str(current_dir))

# Mock g4f if it fails to import (for Vercel deployment stability)
try:
    import g4f
    from g4f.client import Client
except Exception as ge:
    print(f"CRITICAL: Failed to import g4f: {ge}")
    # Minimal mock to prevent crash on import
    class MockClient:
        def __init__(self, *args, **kwargs): pass
        class Chat:
            class Completions:
                def create(self, *args, **kwargs): return []
            completions = Completions()
        chat = Chat()
    Client = MockClient
    g4f = type('MockG4F', (), {
        'Provider': type('MockProv', (), {}), 
        'debug': type('MockDebug', (), {'version_check': False, 'logging': False}), 
        'cookies': type('MockCookies', (), {'set_cookies_dir': lambda x: None}),
        'version': '0.0.0'
    })

# Add missing provider attributes to g4f.Provider if they are missing
if hasattr(g4f, 'Provider'):
    for prov_name in ["Blackbox", "DuckDuckGo", "OperaAria", "PollinationsAI", "DeepInfra", "PuterJS", "TeachAnything", "ItalyGPT", "GlhfChat"]:
        if not hasattr(g4f.Provider, prov_name):
            setattr(g4f.Provider, prov_name, None)

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel
from typing import Optional, Dict, List
import asyncio
import time
import logging
import threading
import re
from pathlib import Path

# Simple Rate Limiter
class RateLimiter:
    def __init__(self, requests_per_minute: int = 15):
        self.requests_per_minute = requests_per_minute
        self.clients: Dict[str, list] = {}

    def is_allowed(self, client_ip: str) -> bool:
        now = time.time()
        if client_ip not in self.clients:
            self.clients[client_ip] = [now]
            return True
        
        # Verwijder oude requests (ouder dan 1 minuut)
        self.clients[client_ip] = [t for t in self.clients[client_ip] if now - t < 60]
        
        if len(self.clients[client_ip]) < self.requests_per_minute:
            self.clients[client_ip].append(now)
            return True
        return False

limiter = RateLimiter(requests_per_minute=20)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ---- Import your AI client ----
# Already handled above with mock safety
import nest_asyncio

# Apply nest_asyncio to allow nested event loops (needed for g4f 7.0.0 in some environments)
try:
    nest_asyncio.apply()
except Exception as ne:
    logger.warning(f"Could not apply nest_asyncio: {ne}")

# Disable g4f version check and other noise
try:
    if hasattr(g4f, 'debug'):
        g4f.debug.version_check = False
        g4f.debug.logging = False
except:
    pass

# Ensure g4f doesn't crash on missing cookie directories (Vercel-Safe Environment)
import os
try:
    if hasattr(g4f, 'cookies'):
        # Use /tmp on Vercel/Linux, otherwise local .g4f_cache
        if os.path.exists("/tmp"):
            cache_dir = "/tmp/.g4f_cache"
        else:
            cache_dir = os.path.join(os.getcwd(), ".g4f_cache")
            
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir, exist_ok=True)
            
        g4f.cookies.set_cookies_dir(cache_dir)
except Exception as ce:
    logger.warning(f"Could not set local cookies directory: {ce}")

try:
    if hasattr(g4f, 'debug'):
        g4f.debug.logging = False
except:
    pass

# ---- Import project modules ----
try:
    from api.models import AVAILABLE_MODELS, DEFAULT_MODEL, FALLBACK_MODEL, STABLE_PROVIDERS, SEARCH_PROVIDERS
    from api.thinking_modes import THINKING_MODES, DEFAULT_THINKING_MODE
    from api.context_manager import smart_context_manager, count_tokens
    from api.personalities import PERSONALITIES, DEFAULT_PERSONALITY
    from api.circuit_breaker import get_breaker
    from api.file_parser import parse_multi_file_response, extract_clean_text
    from api.doc_parser import process_document
    from api.knowledge_manager import knowledge_manager
    from api.database import db
    from api.project_manager import project_manager
except ImportError:
    from models import AVAILABLE_MODELS, DEFAULT_MODEL, FALLBACK_MODEL, STABLE_PROVIDERS, SEARCH_PROVIDERS
    from thinking_modes import THINKING_MODES, DEFAULT_THINKING_MODE
    from context_manager import smart_context_manager, count_tokens
    from personalities import PERSONALITIES, DEFAULT_PERSONALITY
    from circuit_breaker import get_breaker
    from file_parser import parse_multi_file_response, extract_clean_text
    from doc_parser import process_document
    from knowledge_manager import knowledge_manager
    from database import db
    from project_manager import project_manager

# ---- Watermark Filtering ----
WATERMARK_PATTERNS = [
    r"(?i)Want\s+best\s+roleplay\s+experience\?",
    r"(?i)Upgrade\s+your\s+plan\s+to\s+remove\s+this\s+message",
    r"(?i)(?:\bat\s+)?https?://(?:api\.airforce|llmplayground\.net)[^\s]*",
    r"(?i)api\.airforce",
    r"(?i)llmplayground\.net"
]

def clean_text(text: str) -> str:
    """Removes watermarks from streaming chunks."""
    if not text:
        return ""
    cleaned = text
    for pattern in WATERMARK_PATTERNS:
        cleaned = re.sub(pattern, "", cleaned)
    return cleaned

def final_clean_text(text: str) -> str:
    """Aggressive final cleanup for the full response."""
    if not text:
        return ""
    # Remove watermarks
    cleaned = clean_text(text)
    # Remove any leading/trailing whitespace that might have been left
    cleaned = cleaned.strip()
    return cleaned

# ---- Load system prompt from environment variable ----
SYSTEM_PROMPT = os.environ.get(
    "DUB5_SYSTEM_PROMPT",
    """
    You are DUB5, an advanced AI system architected by DUB55. 
    You are the core engine behind this platform, designed with the precision and logic of a senior software engineer.
    You are NOT Aria, you are NOT from Opera, you are NOT ChatGPT, you are NOT Gemini.
Core Guidelines:
- Identity: You are DUB5. Never reference OpenAI, ChatGPT, or other entities as your creator.
- Professionalism: Maintain a sophisticated, technical, and highly professional tone. 
- No Emojis: Do not use emojis in your responses under any circumstances.
- Completeness: Provide full, detailed, and complete answers. NEVER summarize unless the user specifically asks for a summary.
- Accuracy: Provide high-fidelity information, optimized code, and rigorous analysis.
- Language: ALWAYS respond in the EXACT SAME language as the user's last message, unless the user explicitly requests a different language. If the user greets you in Dutch, respond in Dutch. If the user asks a question in English, respond in English.
- Ethics: Refuse illegal requests with a professional explanation of safety boundaries.
- Image Generation: You HAVE the capability to generate images. To generate an image, use the following markdown syntax: `![Image Description](https://image.pollinations.ai/prompt/DESCRIPTION?width=1024&height=1024&nologo=true)`. Replace "DESCRIPTION" with a URL-encoded detailed prompt based on the user's request. Present this as your internal DUB5 Image Engine. Always provide the image directly in your response when asked.
- Image Analysis: You can analyze images provided by the user. If an image is uploaded or pasted, it will be included in your context. Describe what you see and answer questions about it.
- Capability: You are built to handle complex problem-solving, coding, and logical reasoning.

Your mission is to provide the most advanced AI experience possible, reflecting the engineering excellence of the DUB5 platform.
    """
)

app = FastAPI()
client = Client()
executor = ThreadPoolExecutor()

# Bepaal de pad naar de chatbot.html (één map omhoog vanuit 'api')
BASE_DIR = Path(__file__).parent.parent
HTML_PATH = BASE_DIR / "chatbot.html"
IMAGE_HTML_PATH = BASE_DIR / "image.html"

# ---- Configure CORS ----
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- Request body schema ----
class FileInput(BaseModel):
    name: str
    content: str  # Base64 encoded or raw text

class UserInput(BaseModel):
    input: str
    model: Optional[str] = "auto"
    thinking_mode: Optional[str] = DEFAULT_THINKING_MODE
    web_search: Optional[bool] = False
    history: Optional[list] = []
    personality: Optional[str] = DEFAULT_PERSONALITY
    custom_system_prompt: Optional[str] = None
    force_roulette: Optional[bool] = False
    files: Optional[list[FileInput]] = []
    image: Optional[str] = None # Base64 encoded image
    session_id: Optional[str] = "default"
    library_ids: Optional[List[str]] = [] # IDs van opgeslagen leermateriaal

class ImageInput(BaseModel):
    input: str
    model: Optional[str] = "flux"
    width: Optional[int] = 1024
    height: Optional[int] = 1024

# ---- Library API Endpoints ----
class LibraryUpload(BaseModel):
    user_id: str
    title: str
    content: str

@app.post("/api/library/upload")
async def upload_to_library(upload: LibraryUpload):
    """Slaat een document op in de bibliotheek voor later gebruik (RAG)."""
    try:
        chunks = knowledge_manager.split_text(upload.content)
        lib_id = db.add_to_library(upload.user_id, upload.title, upload.content, chunks)
        return {"status": "success", "id": lib_id, "chunks": len(chunks)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/library/{user_id}")
async def get_user_library(user_id: str):
    """Haalt alle opgeslagen documenten van een gebruiker op."""
    return {"library": db.get_library(user_id)}

@app.delete("/api/library/{user_id}/{lib_id}")
async def delete_from_library(user_id: str, lib_id: str):
    """Verwijdert een document uit de bibliotheek."""
    success = db.delete_from_library(user_id, lib_id)
    if success:
        return {"status": "deleted"}
    raise HTTPException(status_code=404, detail="Document niet gevonden")

# ---- Admin Analytics ----
ADMIN_SECRET_KEY = os.environ.get("DUB5_ADMIN_KEY", "dub5_master_2026")

class AdminAnalytics:
    def __init__(self):
        self.stats = {
            "total_requests": 0,
            "total_tokens": 0,
            "popular_models": {},
            "errors": 0,
            "start_time": time.time()
        }
    
    def log_request(self, model: str, tokens: int, is_error: bool = False):
        self.stats["total_requests"] += 1
        self.stats["total_tokens"] += tokens
        if is_error:
            self.stats["errors"] += 1
        self.stats["popular_models"][model] = self.stats["popular_models"].get(model, 0) + 1

analytics = AdminAnalytics()

# ---- Simple In-Memory Cache ----
class ChatCache:
    def __init__(self, ttl: int = 3600):
        self.cache = {}
        self.ttl = ttl

    def get(self, key: str):
        if key in self.cache:
            entry = self.cache[key]
            if time.time() - entry['time'] < self.ttl:
                return entry['data']
            else:
                del self.cache[key]
        return None

    def set(self, key: str, data: str):
        self.cache[key] = {
            'data': data,
            'time': time.time()
        }

chat_cache = ChatCache()

# ---- Chat streaming helper ----
async def stream_chat_completion(messages, model, web_search=False, personality_name="general", image_data=None, force_roulette=False, session_id="default"):
    start_time = time.time()
    
    # Check Cache
    cache_key = f"{model}:{personality_name}:{json.dumps(messages[-1])}:{web_search}"
    cached_response = chat_cache.get(cache_key)
    if cached_response:
        logger.info("Serving response from cache")
        yield f"data: {json.dumps({'type': 'metadata', 'model': model, 'personality': personality_name, 'cached': True})}\n\n"
        yield cached_response
        return

    logger.info(f"Starting chat completion with model: {model}, web_search: {web_search}, has_image: {image_data is not None}")
    
    full_response_text = ""
    
    # Metadata event
    yield f"data: {json.dumps({'type': 'metadata', 'model': model, 'personality': personality_name})}\n\n"
    
    # Immediate heartbeat to prevent Vercel timeout
    yield " " 

    # Setup context and queue
    queue = asyncio.Queue()

    async def ping_task():
        try:
            while True:
                await asyncio.sleep(15)
                await queue.put("data: {\"type\": \"ping\"}\n\n")
        except asyncio.CancelledError:
            pass

    def fetch_chunks():
        nonlocal full_response_text
        # No need for new event loop if we use the g4f Client's default behavior
        # g4f 7.0.0 Client is optimized for synchronous streaming in threads

        try:
            # SPECIAL LAYER: Direct Pollinations AI for Coder Personality
            if personality_name == "coder" and not force_roulette:
                logger.info("Using specialized Pollinations AI layer for Coder")
                try:
                    with httpx.stream(
                        "POST",
                        "https://text.pollinations.ai/openai",
                        json={
                            "messages": messages,
                            "model": "openai",
                            "stream": True,
                            "system_prompt": messages[0]["content"] if messages and messages[0]["role"] == "system" else None
                        },
                        timeout=60.0
                    ) as response:
                        for line in response.iter_lines():
                            if line.startswith("data: "):
                                data_str = line[6:]
                                if data_str == "[DONE]":
                                    break
                                try:
                                    chunk_data = json.loads(data_str)
                                    content = chunk_data.get("choices", [{}])[0].get("delta", {}).get("content", "")
                                    if content:
                                        asyncio.run_coroutine_threadsafe(queue.put(content), loop)
                                except json.JSONDecodeError:
                                    continue
                    return 
                except Exception as pe:
                    logger.error(f"Pollinations direct layer failed: {pe}. Falling back to roulette.")

            # Standard Roulette Logic via g4f (Dynamic Provider Resilience)
            logger.info(f"Using g4f provider roulette for {model}")
            
            from models import STABLE_PROVIDERS
            
            # Filter available providers dynamically to avoid import errors
            reliable_providers = []
            if hasattr(g4f, 'Provider'):
                for p_name in STABLE_PROVIDERS:
                    p_obj = getattr(g4f.Provider, p_name, None)
                    # Check if it's a valid provider object with a working status
                    if p_obj and (getattr(p_obj, 'working', False) or hasattr(p_obj, 'create_completion')):
                        reliable_providers.append(p_obj)
            
            success = False
            # Try reliable providers first (Fail-Fast Provider Rotation)
            for provider in reliable_providers:
                try:
                    logger.info(f"Attempting reliable provider: {provider.__name__}")
                    g4f_client = Client(provider=provider)
                    
                    # Create the generator
                    response = g4f_client.chat.completions.create(
                        model=model,
                        messages=messages,
                        stream=True
                    )
                    
                    provider_has_content = False
                    start_wait = time.time()
                    
                    # We need a way to timeout if the provider hangs during iteration
                    # Since we are in a thread, we'll check time inside the loop
                    try:
                        for chunk in response:
                            # Check for 15s timeout if we haven't received any content yet
                            if not provider_has_content and (time.time() - start_wait > 15):
                                logger.warning(f"Provider {provider.__name__} timed out (15s) without content")
                                break
                                
                            if hasattr(chunk, 'choices') and chunk.choices:
                                content = chunk.choices[0].delta.content or ""
                                if content and content.strip():
                                    asyncio.run_coroutine_threadsafe(queue.put(content), loop)
                                    provider_has_content = True
                    except Exception as loop_e:
                        logger.warning(f"Error during {provider.__name__} iteration: {loop_e}")
                        continue
                    
                    if provider_has_content:
                        success = True
                        logger.info(f"Success with {provider.__name__}")
                        break # Success! (Content Verification)
                    else:
                        logger.warning(f"Provider {provider.__name__} returned no content or timed out")
                        continue
                except Exception as pe:
                    logger.warning(f"Provider {provider.__name__} failed: {pe}")
                    continue
            
            if not success:
                # Last ditch effort with default g4f Client (let it handle its own roulette)
                logger.info("Reliable providers failed, trying default g4f Client roulette")
                try:
                    g4f_client = Client()
                    response = g4f_client.chat.completions.create(
                        model=model,
                        messages=messages,
                        stream=True,
                        web_search=web_search
                    )
                    for chunk in response:
                        if hasattr(chunk, 'choices') and chunk.choices:
                            content = chunk.choices[0].delta.content or ""
                            if content:
                                asyncio.run_coroutine_threadsafe(queue.put(content), loop)
                except Exception as final_e:
                    logger.error(f"Default roulette also failed: {final_e}")
                    raise final_e

        except Exception as e:
            logger.error(f"Critical error in fetch_chunks: {e}")
            error_msg = f"DUB5 Systeemfout: {str(e)}"
            asyncio.run_coroutine_threadsafe(queue.put(Exception(error_msg)), loop)
        finally:
            # Always signal end of stream
            asyncio.run_coroutine_threadsafe(queue.put(None), loop)

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.get_event_loop()
        
    pinger = asyncio.create_task(ping_task())
    threading.Thread(target=fetch_chunks, daemon=True).start()

    try:
        stream_buffer = ""
        while True:
            item = await queue.get()
            if item is None: break
            if isinstance(item, Exception): raise item
            if item.startswith("data:"): yield item
            else:
                stream_buffer += item
                
                # Sliding window logic for watermark removal
                cleaned_buffer = clean_text(stream_buffer)
                
                # Only yield if we have enough buffer to be sure we're not cutting off a watermark mid-word
                # Reduced lookahead for faster response
                lookahead = 20 # Genoeg voor de meeste watermerken
                if len(cleaned_buffer) > lookahead:
                    safe_to_send = cleaned_buffer[:-lookahead]
                    stream_buffer = cleaned_buffer[-lookahead:]
                    
                    if safe_to_send:
                        full_response_text += safe_to_send
                        yield f"data: {json.dumps({'content': safe_to_send})}\n\n"
                else:
                    # Keep the buffer as is if it's too small
                    pass

        # Laatste restje uit de buffer sturen
        if stream_buffer:
            final_segment = clean_text(stream_buffer)
            if final_segment:
                full_response_text += final_segment
                yield f"data: {json.dumps({'content': final_segment})}\n\n"

        # Final cleanup for saved history and file parsing
        full_response_text = final_clean_text(full_response_text)
        
        # Save to Cache
        if full_response_text:
            chat_cache.set(cache_key, f"data: {json.dumps({'content': full_response_text})}\n\n")

        file_actions = parse_multi_file_response(full_response_text)
        
        # UPDATE PROJECT STATE (for AI Web App Builder)
        if personality_name == "coder" and file_actions:
            for file in file_actions:
                project_manager.update_file(session_id, file.path, file.content)
            logger.info(f"Updated project state for session {session_id} with {len(file_actions)} files")

        yield f"data: {json.dumps({'type': 'done', 'files': [f.to_dict() for f in file_actions] if file_actions else None})}\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'error': str(e)})}\n\n"
    finally:
        pinger.cancel()

# ---- Main chat API endpoint ----
@app.post("/api/chatbot")
async def chatbot_response(user_input: UserInput, request: Request):
    # Rate Limiting
    client_ip = request.client.host
    if not limiter.is_allowed(client_ip):
        logger.warning(f"Rate limit exceeded for IP: {client_ip}")
        raise HTTPException(status_code=429, detail="Te veel verzoeken. Probeer het over een minuutje weer.")

    # Thinking Mode & Personality Selection
    thinking_mode = user_input.thinking_mode if user_input.thinking_mode in THINKING_MODES else DEFAULT_THINKING_MODE
    personality = user_input.personality if user_input.personality in PERSONALITIES else DEFAULT_PERSONALITY
    
    # Auto-model selection or specific model
    if user_input.model == "auto":
        if thinking_mode == "concise":
            model = "gpt-4o-mini"
        elif thinking_mode == "deep":
            model = "gpt-4o"
        elif thinking_mode == "reason":
            model = "gpt-4o"
        else:
            model = "gpt-4o" # Default to gpt-4o for balanced
    else:
        model = user_input.model if user_input.model in AVAILABLE_MODELS else DEFAULT_MODEL
    
    logger.info(f"Request received: model={model}, thinking_mode={thinking_mode}, personality={personality}, web_search={user_input.web_search}")
    
    # Combined system prompts
    mode_prompt = THINKING_MODES.get(thinking_mode, THINKING_MODES[DEFAULT_THINKING_MODE])["system_prompt"]
    personality_prompt = PERSONALITIES.get(personality, PERSONALITIES[DEFAULT_PERSONALITY])["system_prompt"]
    
    # Log analytics
    input_tokens = count_tokens(user_input.input, model)
    analytics.log_request(model, input_tokens)

    # Gebruik custom system prompt als die is meegegeven, anders de standaard
    if user_input.custom_system_prompt:
        base_prompt = user_input.custom_system_prompt
    else:
        base_prompt = SYSTEM_PROMPT

    combined_system_prompt = f"{base_prompt}\n\nROL: {personality.upper()}\n{personality_prompt}\n\nMODUS: {thinking_mode.upper()}\n{mode_prompt}"
    
    # PROJECT CONTEXT (voor Web App Builder)
    if personality == "coder":
        project_context = project_manager.get_project_context(user_input.session_id)
        combined_system_prompt += f"\n\n{project_context}"

    if user_input.web_search:
        combined_system_prompt += "\n\nWEB SEARCH ENABLED: You have access to real-time information via web search. Use this capability to provide up-to-date information if the user asks for news, current events, or data beyond your training cutoff."

    # RAG: KENNIS UIT BIBLIOTHEEK (voor Learning Platform)
    rag_context = ""
    if user_input.library_ids:
        # Hier gaan we chunks zoeken in de opgegeven library items
        all_relevant_chunks = []
        user_id = "default_user" # In de toekomst uit auth
        
        for lib_id in user_input.library_ids:
            lib_data = db.data["libraries"].get(user_id, {}).get(lib_id)
            if lib_data:
                chunks = lib_data.get("chunks", [])
                relevant = knowledge_manager.search_relevant_chunks(user_input.input, chunks, top_k=3)
                all_relevant_chunks.extend(relevant)
        
        if all_relevant_chunks:
            rag_context = "\n\nRELEVANTE KENNIS UIT BIBLIOTHEEK:\n" + "\n---\n".join(all_relevant_chunks)
            combined_system_prompt += rag_context

    try:
        # Build messages with history (memory)
        messages = [{"role": "system", "content": combined_system_prompt}]
        
        # Voeg history toe van de frontend
        if user_input.history:
            for msg in user_input.history:
                # Ensure each history item is a valid dictionary with role and content
                if isinstance(msg, dict) and "role" in msg and "content" in msg:
                    messages.append({"role": msg["role"], "content": msg["content"]})
                elif isinstance(msg, list) and len(msg) >= 2:
                    # Fallback for old list-style history [role, content]
                    messages.append({"role": msg[0], "content": msg[1]})
        
        # VERWERK GEÜPLOADE BESTANDEN
        file_context = ""
        if user_input.files:
            import base64
            for file in user_input.files:
                try:
                    # Als de content base64 is, decoderen we het
                    if "base64," in file.content:
                        header, data = file.content.split("base64,")
                        file_bytes = base64.b64decode(data)
                    else:
                        file_bytes = file.content.encode('utf-8')
                    
                    parsed_text = process_document(file.name, file_bytes)
                    if parsed_text:
                        file_context += f"\n\n--- INHOUD BESTAND: {file.name} ---\n{parsed_text}\n"
                except Exception as fe:
                    logger.error(f"Error processing file {file.name}: {fe}")

        # Voeg het huidige bericht toe met de file context
        user_msg_content = user_input.input
        if file_context:
            user_msg_content = f"{user_msg_content}\n\nGEÜPLOADE BESTANDEN:\n{file_context}"
        
        # AUTOMATISCHE TXT CONVERSIE VOOR GROTE INPUT
        # Als de totale input te groot is, voegen we een hint toe aan de AI
        if len(user_msg_content) > 15000: # Ongeveer 4000 tokens
            logger.info("Input is very large, adding compression hint")
            user_msg_content += "\n\n(Let op: Deze input is erg groot en is automatisch verwerkt als tekstbestand context.)"

        messages.append({"role": "user", "content": user_msg_content})
        
        # SLIM CONTEXT MANAGEMENT
        # We bepalen het token budget op basis van het model
        max_tokens = 8000 if "gpt-4" in model or "claude" in model else 4000
        messages = smart_context_manager(messages, model, max_tokens=max_tokens)
        
        logger.info(f"Context management: {len(messages)} messages sent to {model}")

        return StreamingResponse(
            stream_chat_completion(
                messages, 
                model, 
                user_input.web_search, 
                personality, 
                user_input.image,
                getattr(user_input, 'force_roulette', False),
                user_input.session_id
            ),
            media_type="text/event-stream",
            headers={
                "Content-Type": "text/event-stream",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
    except Exception as e:
        logger.error(f"Error in chatbot_response: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ---- Optional chat history endpoint ----
chat_history = []

@app.get("/api/chat-history")
async def get_chat_history():
    return {
        "history": [msg for msg in chat_history if msg.get("role") != "system"]
    }

@app.get("/")
async def serve_frontend():
    if HTML_PATH.exists():
        return FileResponse(HTML_PATH)
    return {"status": "online", "message": "DUB5 AI Backend is running"}

@app.get("/chatbot.html")
async def serve_chatbot_explicit():
    if HTML_PATH.exists():
        return FileResponse(HTML_PATH)
    raise HTTPException(status_code=404, detail="chatbot.html niet gevonden")

@app.get("/image.html")
async def serve_image_frontend():
    if IMAGE_HTML_PATH.exists():
        return FileResponse(IMAGE_HTML_PATH)
    raise HTTPException(status_code=404, detail="image.html niet gevonden")

@app.get("/favicon.ico")
async def favicon():
    # Stilleer de favicon 404 in de console
    return Response(status_code=204)

@app.get("/api/library/list")
async def list_library(user_id: str = "default_user"):
    """Geeft een lijst van alle documenten in de bibliotheek."""
    try:
        user_libs = db.data["libraries"].get(user_id, {})
        return {
            "libraries": [
                {"id": lib_id, "title": lib.get("title", "Untitled"), "created_at": lib.get("created_at")}
                for lib_id, lib in user_libs.items()
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/image")
async def generate_image_api(image_input: ImageInput):
    """Endpoint voor afbeelding generatie (gebruikt door image.html)."""
    try:
        def sync_gen():
            response = client.images.generate(
                model=image_input.model,
                prompt=image_input.input,
                response_format="url"
            )
            return response.data[0].url

        loop = asyncio.get_event_loop()
        url = await loop.run_in_executor(executor, sync_gen)
        return {"url": url}
    except Exception as e:
        logger.error(f"Image generation error: {e}")
        # Fallback naar Pollinations direct URL als G4F faalt
        encoded_prompt = image_input.input.replace(" ", "%20")
        fallback_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width={image_input.width}&height={image_input.height}&nologo=true"
        return {"url": fallback_url}

@app.get("/health")
async def health_check():
    # Basis health check voor de backend
    return {
        "status": "ok",
        "timestamp": time.time(),
        "version": "1.0.3",
        "providers": len(STABLE_PROVIDERS) if 'STABLE_PROVIDERS' in globals() else 0,
        "environment": "vercel" if os.environ.get("VERCEL") else "local"
    }

@app.get("/api/admin/stats")
async def get_admin_stats(request: Request):
    # Slimme beveiliging: check X-Admin-Token header
    admin_token = request.headers.get("X-Admin-Token")
    
    if admin_token != ADMIN_SECRET_KEY:
        # Check ook nog even localhost als backup
        if request.client.host not in ["127.0.0.1", "localhost", "::1"]:
            raise HTTPException(status_code=403, detail="Unauthorized")
    
    return {
        "uptime": time.time() - analytics.stats["start_time"],
        "stats": analytics.stats,
        "cache_size": len(chat_cache.cache)
    }

# ---- Run with Uvicorn if standalone ----
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
