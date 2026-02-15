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
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type

from api.config import Config

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
    from .context_manager import smart_context_manager, count_tokens
    from .personalities import PERSONALITIES, DEFAULT_PERSONALITY
    from .circuit_breaker import get_breaker
    from .file_parser import parse_multi_file_response, extract_clean_text
    from .doc_parser import process_document
    from .knowledge_manager import knowledge_manager
    from .database import db
    from .project_manager import project_manager

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
SYSTEM_PROMPT = Config.DUB5_SYSTEM_PROMPT

# ---- Initialize FastAPI ----
# Gebruik root_path="/api" als we op Vercel draaien om de routing goed te laten verlopen
app = FastAPI(root_path="/api" if Config.VERCEL_ENV else "")
client = Client()
executor = ThreadPoolExecutor(max_workers=10)

# Versie van de backend
VERSION = "1.0.7"

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
ADMIN_SECRET_KEY = Config.ADMIN_SECRET_KEY

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

# ---- Provider Selection for g4f ----

# Performance tracking for g4f providers
g4f_provider_performance: Dict[str, Dict[str, Any]] = {}

def initialize_g4f_provider_performance():
    global g4f_provider_performance
    for provider_name in STABLE_PROVIDERS:
        g4f_provider_performance[provider_name] = {
            "success_count": 0,
            "failure_count": 0,
            "total_latency": 0.0,
            "last_used_time": 0.0,
            "last_failure_time": 0.0,
            "consecutive_failures": 0,
            "priority_score": 1.0 # Higher score means higher priority
        }

# Initialize performance data on startup
initialize_g4f_provider_performance()

def get_best_g4f_provider():
    """
    Selects the best available g4f provider based on a predefined list of stable providers.
    In a more advanced setup, this would involve real-time performance tracking.
    """
    available_g4f_providers = []
    for provider_name in dir(g4f.Provider):
        if not provider_name.startswith("__") and provider_name.isidentifier():
            provider_class = getattr(g4f.Provider, provider_name)
            if provider_class is not None and hasattr(provider_class, '__call__'): # Check if it's a callable class (a provider)
                available_g4f_providers.append(provider_name)

    # Filter by STABLE_PROVIDERS from models.py
    # Ensure STABLE_PROVIDERS is a list of strings
    stable_providers_list = [p.strip() for p in STABLE_PROVIDERS if isinstance(p, str)]
    
    # Find intersection of available and stable providers
    usable_providers = [p for p in available_g4f_providers if p in stable_providers_list]

    if not usable_providers:
        logger.warning("No usable g4f providers found from STABLE_PROVIDERS. Falling back to any available provider.")
        # Fallback to any available provider if no stable ones are found
        usable_providers = available_g4f_providers
        if not usable_providers:
            logger.error("No g4f providers available at all.")
            return None

    # Intelligent provider selection based on performance metrics
    scored_providers = []
    current_time = time.time()
    
    for provider_name in usable_providers:
        performance = g4f_provider_performance.get(provider_name, {
            "success_count": 0, "failure_count": 0, "total_latency": 0.0,
            "last_used_time": 0.0, "last_failure_time": 0.0, "consecutive_failures": 0
        })

        score = 1.0 # Base score

        # Penalize providers with recent consecutive failures
        if performance["consecutive_failures"] > 2 and (current_time - performance["last_failure_time"]) < 300: # Cooldown for 5 minutes
            logger.warning(f"Provider {provider_name} is in cooldown due to {performance['consecutive_failures']} consecutive failures.")
            continue # Skip this provider for now

        # Factor in success rate
        total_calls = performance["success_count"] + performance["failure_count"]
        if total_calls > 0:
            success_rate = performance["success_count"] / total_calls
            score *= (0.5 + success_rate) # Boost for higher success rate (0.5 to 1.5 multiplier)
        
        # Factor in average latency (lower is better)
        if performance["success_count"] > 0:
            avg_latency = performance["total_latency"] / performance["success_count"]
            score *= (1.0 / (1.0 + avg_latency / 5.0)) # Inverse relationship, normalize by a typical latency (e.g., 5 seconds)
        
        # Factor in last used time (prefer less recently used to distribute load)
        time_since_last_used = current_time - performance["last_used_time"]
        score *= (1.0 + time_since_last_used / 3600.0) # Small boost for providers not used in the last hour

        scored_providers.append((provider_name, score))

    if not scored_providers:
        logger.warning("No providers passed the scoring criteria. Falling back to random selection from all usable providers.")
        selected_provider_name = random.choice(usable_providers)
    else:
        # Sort by score in descending order and pick the best one
        scored_providers.sort(key=lambda x: x[1], reverse=True)
        selected_provider_name = scored_providers[0][0]

    logger.info(f"Selected g4f provider: {selected_provider_name} (Score: {scored_providers[0][1] if scored_providers else 'N/A'})")
    return getattr(g4f.Provider, selected_provider_name)



async def stream_chat_completion(
    messages: List[Dict[str, str]],
    model: str,
    web_search: bool,
    personality_name: str,
    image_data: Optional[str],
    force_roulette: bool,
    session_id: str
) -> AsyncGenerator[str, None]:
    logger.info(f"stream_chat_completion called for session_id: {session_id}")
    start_time = time.time()
    
    # Check Cache
    cache_key = f"{model}:{personality_name}:{json.dumps(messages[-1])}:{web_search}"
    cached_response = chat_cache.get(cache_key)
    if cached_response:
        logger.info("Serving response from cache")
        yield f"data: {json.dumps({'type': 'metadata', 'model': model, 'personality': personality_name, 'cached': True})}\n\n"
        yield cached_response
        return

    logger.info(f"Starting chat completion for session_id: {session_id}, model: {model}, personality: {personality_name}, web_search: {web_search}")
    
    # Metadata event
    yield f"data: {json.dumps({'type': 'metadata', 'model': model, 'personality': personality_name, 'session_id': session_id})}\n\n"
    
    # Immediate heartbeat to prevent Vercel timeout
    yield ": heartbeat\n\n" 

    full_response_text = ""
    try:
        async for chunk in fetch_chunks_async(
            messages, 
            model, 
            web_search, 
            personality_name, 
            image_data, 
            force_roulette, 
            session_id
        ):
            if chunk is None: # Sentinel value for end of stream
                break
            if isinstance(chunk, Exception):
                raise chunk
            
            cleaned_chunk = clean_text(chunk) if chunk else ""
            if cleaned_chunk:
                yield f"data: {json.dumps({'type': 'chunk', 'content': cleaned_chunk})}\n\n"
                full_response_text += cleaned_chunk
    except Exception as e:
        logger.error(f"Error during chat streaming for session_id: {session_id}: {e}", exc_info=True)
        yield f"data: {json.dumps({'type': 'error', 'content': f'Error during streaming: {e}'})}\n\n"
    finally:
        # Ensure the queue is cleared and the thread is properly shut down if needed
        logger.info(f"Stream finished for session_id: {session_id}. Total response length: {len(full_response_text)}")
        if full_response_text:
            chat_cache.set(cache_key, full_response_text)
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Log performance for analytics
        analytics.log_request(model, count_tokens(full_response_text), is_error=False)
        
        # Final event
        yield f"data: {json.dumps({'type': 'end', 'content': 'Stream finished', 'duration': duration})}\n\n"

async def fetch_chunks_async(
    messages: List[Dict[str, str]],
    model: str,
    web_search: bool,
    personality_name: str,
    image_data: Optional[str],
    force_roulette: bool,
    session_id: str
) -> AsyncGenerator[str, None]:
    logger.info(f"fetch_chunks_async started for session_id: {session_id}")
    
    try:
        # Primary: Try g4f Client first
        selected_g4f_provider = get_best_g4f_provider()
        if not selected_g4f_provider:
            logger.warning("No suitable g4f provider found, falling back to Pollinations AI.")
        else:
            try:
                logger.info(f"Using g4f Client with provider: {selected_g4f_provider.__name__} for model: {model}")
                g4f_client = Client(provider=selected_g4f_provider)
                logger.info(f"Attempting g4f chat completion with provider: {selected_g4f_provider.__name__}")
                
                provider_name_str = selected_g4f_provider.__name__
                start_time_g4f = time.perf_counter()

                response = await g4f_client.chat.completions.create(
                    model=model,
                    messages=messages,
                    stream=True
                )
                for chunk in response:
                    content = chunk.choices[0].delta.content
                    if content:
                        logger.debug(f"g4f AI: Yielding content: {content[:50]}...")
                        yield content
                
                end_time_g4f = time.perf_counter()
                latency = end_time_g4f - start_time_g4f
                if provider_name_str in g4f_provider_performance:
                    g4f_provider_performance[provider_name_str]["success_count"] += 1
                    g4f_provider_performance[provider_name_str]["total_latency"] += latency
                    g4f_provider_performance[provider_name_str]["last_used_time"] = end_time_g4f
                    g4f_provider_performance[provider_name_str]["consecutive_failures"] = 0
                logger.info(f"g4f call with {provider_name_str} successful in {latency:.4f} seconds.")
                yield None # Signal end of stream
                return

            except Exception as g4f_e:
                end_time_g4f = time.perf_counter()
                latency = end_time_g4f - start_time_g4f
                if provider_name_str in g4f_provider_performance:
                    g4f_provider_performance[provider_name_str]["failure_count"] += 1
                    g4f_provider_performance[provider_name_str]["last_failure_time"] = end_time_g4f
                    g4f_provider_performance[provider_name_str]["consecutive_failures"] += 1
                logger.error(f"g4f call with {provider_name_str} failed after {latency:.4f} seconds: {g4f_e}", exc_info=True)
                logger.info("g4f failed, falling back to Pollinations AI")

        # Fallback: Use Pollinations AI
        logger.info(f"Using Pollinations AI as fallback for session_id: {session_id}")
        try:
            start_time_pollinations = time.perf_counter()
            logger.info(f"Entering Pollinations AI call for session_id: {session_id}")
            
            # Direct Pollinations API call
            pollinations_url = "https://text.pollinations.ai/openai"
            pollinations_payload = {
                "messages": messages,
                "model": "openai",
                "stream": True
            }
            
            logger.info(f"Making direct Pollinations AI request: {pollinations_url}")
            async with httpx.AsyncClient(timeout=60.0) as client:
                async with client.stream(
                    "POST",
                    pollinations_url,
                    json=pollinations_payload
                ) as response:
                    logger.info(f"Pollinations Response Status: {response.status_code}")
                    if response.is_success:
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
                                            logger.debug(f"Pollinations AI: Yielding content: {content[:50]}...")
                                            yield content
                                    except json.JSONDecodeError:
                                        continue
                                    except Exception as chunk_e:
                                        logger.error(f"Error processing Pollinations chunk: {chunk_e}")
                                        continue
                        
                        # Process remaining buffer
                        if buffer.strip():
                            line = buffer.decode("utf-8").strip()
                            if line.startswith("data: "):
                                data_str = line[6:]
                                if data_str != "[DONE]":
                                    try:
                                        chunk_data = json.loads(data_str)
                                        content = chunk_data.get("choices", [{}])[0].get("delta", {}).get("content", "")
                                        if content:
                                            yield content
                                    except json.JSONDecodeError:
                                        pass
                                    except Exception as chunk_e:
                                        logger.error(f"Error processing final Pollinations chunk: {chunk_e}")
                    else:
                        response_body = await response.aread()
                        logger.error(f"Pollinations AI failed with status {response.status_code}: {response_body.decode()}")
                        raise Exception(f"Pollinations AI HTTP error: {response.status_code}")

            end_time_pollinations = time.perf_counter()
            duration_pollinations = end_time_pollinations - start_time_pollinations
            logger.info(f"Pollinations AI call completed in {duration_pollinations:.4f} seconds.")
            yield None # Signal end of stream
            return
            
        except Exception as pollinations_e:
            logger.error(f"Pollinations AI fallback failed: {pollinations_e}", exc_info=True)
            yield Exception(f"Both g4f and Pollinations AI failed. Last error: {pollinations_e}")
            return

    except Exception as e:
        logger.error(f"Error in fetch_chunks_async for session_id: {session_id}: {e}", exc_info=True)
        yield Exception(f"Streaming error: {e}")

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

@app.get("/system-status")
@app.get("/api/system-status")
async def system_status():
    # Basis status check voor de backend
    return {
        "status": "online",
        "timestamp": time.time(),
        "version": VERSION,
        "providers": len(STABLE_PROVIDERS) if 'STABLE_PROVIDERS' in globals() else 0,
        "environment": "vercel" if os.environ.get("VERCEL") else "local",
        "root_path": app.root_path,
        "sys_path": sys.path[:5] # Eerste paar paden voor debug
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
