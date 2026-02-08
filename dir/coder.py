import os
import json
import sys
import httpx
import random
from pathlib import Path

# Voeg de huidige map toe aan sys.path voor imports
current_dir = Path(__file__).parent.absolute()
if str(current_dir) not in sys.path:
    sys.path.append(str(current_dir))

from fastapi import FastAPI, HTTPException, Request
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
from g4f.client import Client
import g4f

# ---- Import project modules ----
from models import AVAILABLE_MODELS, DEFAULT_MODEL, FALLBACK_MODEL, STABLE_PROVIDERS, SEARCH_PROVIDERS
from thinking_modes import THINKING_MODES, DEFAULT_THINKING_MODE
from context_manager import smart_context_manager, count_tokens
from personalities import PERSONALITIES, DEFAULT_PERSONALITY
from circuit_breaker import get_breaker
from file_parser import parse_multi_file_response, extract_clean_text
from doc_parser import process_document

# ---- Watermark Filter ----
WATERMARK_PATTERNS = [
    "Want best roleplay experience?",
    "https://llmplayground.net",
    "Upgrade your plan to remove this message at",
    "https://api.airforce.",
    "https://api.airforce",
    "api.airforce",
    "llmplayground.net"
]

def clean_text(text):
    if not text: return ""
    
    # 1. Define extremely aggressive regex patterns
    # These handle line breaks, multiple spaces, and variations
    patterns = [
        r"(?i)Want\s+best\s+roleplay\s+experience\?",
        r"(?i)Upgrade\s+your\s+plan\s+to\s+remove\s+this\s+message",
        r"(?i)(?:\bat\s+)?https?://(?:api\.airforce|llmplayground\.net)[^\s]*",
        r"(?i)\bat\s+(?=https?://|api\.airforce|llmplayground\.net)", # Standalone 'at' before domain
        r"(?i)api\.airforce",
        r"(?i)llmplayground\.net",
        r"(?i)\s*\bat\s*[\r\n]+\s*\.\s*[\r\n]*", # 'at' followed by '.' with newlines
        r"(?i)\b(at)\b(?=\s*\.|\s*$)", # 'at' followed by a dot or end of string
        r"(?i)--\s*$",
        r"(?m)^\s*\.\s*$", # Standalone dots on a line
        r"(?m)^\s*at\s*$"  # Standalone 'at' on a line
    ]
    
    cleaned = text
    for p in patterns:
        cleaned = re.sub(p, "", cleaned, flags=re.IGNORECASE)
    
    # 2. Collapse excessive newlines (3 or more -> 2)
    cleaned = re.sub(r"(\r\n|\r|\n){3,}", r"\n\n", cleaned)
    
    return cleaned

def final_clean_text(text):
    """Final cleanup including stripping whitespace."""
    return clean_text(text).strip()

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

# Bepaal de pad naar de chatbot.html (één map omhoog vanuit 'dir')
BASE_DIR = Path(__file__).parent.parent
HTML_PATH = BASE_DIR / "chatbot.html"

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
async def stream_chat_completion(messages, model, web_search=False, personality_name="general", image_data=None):
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

    # Queue voor chunks en pings
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
        try:
            # 0. Specialized Builder Layer: Direct Pollinations AI for Coder Personality
            # This provides a more stable and faster experience for the Web App Builder.
            # Only used if not forcing roulette and not using web search.
            if personality_name == "coder" and not web_search and not getattr(user_input, 'force_roulette', False):
                logger.info("Builder Personality detected. Using Direct Pollinations AI Layer.")
                try:
                    # Pollinations AI text API is very fast and reliable for code generation
                    # We use a random seed to ensure unique responses
                    seed = random.randint(1, 1000000)
                    url = f"https://text.pollinations.ai/"
                    
                    payload = {
                        "messages": messages,
                        "model": "openai",
                        "stream": True,
                        "seed": seed
                    }
                    
                    with httpx.stream("POST", url, json=payload, timeout=60.0) as response:
                        if response.status_code == 200:
                            has_content = False
                            for chunk in response.iter_text():
                                if chunk:
                                    # Forward the chunk to the queue
                                    asyncio.run_coroutine_threadsafe(queue.put(chunk), loop)
                                    has_content = True
                            
                            if has_content:
                                asyncio.run_coroutine_threadsafe(queue.put(None), loop)
                                return
                        else:
                            logger.warning(f"Direct Pollinations AI failed with status {response.status_code}")
                except Exception as de:
                    logger.error(f"Direct Pollinations AI error: {de}")
                    # Fall back to g4f providers if direct call fails

            # 1. Web Search Layer: If search is enabled, try search-capable providers first
            if web_search:
                logger.info("Web search enabled. Prioritizing search providers.")
                for s_p_name in SEARCH_PROVIDERS:
                    s_provider = getattr(g4f.Provider, s_p_name, None)
                    if not s_provider: continue
                    
                    try:
                        logger.info(f"Search Layer: Provider={s_p_name}")
                        response = client.chat.completions.create(
                            model="gpt-4o", # Search providers usually handle model mapping internally
                            messages=messages,
                            provider=s_provider,
                            stream=True,
                            timeout=15,
                            web_search=True
                        )
                        has_content = False
                        for chunk in response:
                            if hasattr(chunk.choices[0], 'delta') and hasattr(chunk.choices[0].delta, 'content'):
                                content = chunk.choices[0].delta.content
                                if content:
                                    asyncio.run_coroutine_threadsafe(queue.put(content), loop)
                                    has_content = True
                        if has_content:
                            asyncio.run_coroutine_threadsafe(queue.put(None), loop)
                            return
                    except Exception as se:
                        logger.debug(f"Search Layer Error ({s_p_name}): {se}")
                        continue

            # 2. Primary Attempt: USE ONLY GUARANTEED FREE PROVIDERS FIRST
            # We avoid "auto" select initially because it often hits providers requiring API keys
            # Unique models list to avoid duplicate calls
            priority_models = []
            for m in [model, "gpt-4o", "gpt-4o-mini", "gpt-4", "gpt-3.5-turbo", "llama-3.1-70b"]:
                if m not in priority_models:
                    priority_models.append(m)
            
            # Updated for g4f 7.0.0
            priority_providers = ["PollinationsAI", "ApiAirforce", "DeepInfra", "HuggingFace", "GlhfChat", "Blackbox"]
            
            # SEND INITIAL HEARTBEAT TO FRONTEND
            asyncio.run_coroutine_threadsafe(queue.put(" "), loop) 

            # Step A: Try Priority Providers directly (Fastest & Most Reliable)
            for p_name in priority_providers:
                provider = getattr(g4f.Provider, p_name, None)
                if not provider: 
                    logger.debug(f"Provider {p_name} not found in g4f. Skipping.")
                    continue
                
                # Try gpt-4o-mini first as it's often the most supported free model
                ordered_models = ["gpt-4o-mini", "gpt-4o", "gpt-4", "gpt-3.5-turbo"]
                for target_model in ordered_models:
                    try:
                        logger.info(f"Priority Layer: Provider={p_name}, Model={target_model}")
                        # Use stream=True but also check for content quickly
                        response = client.chat.completions.create(
                            model=target_model, 
                            messages=messages, 
                            provider=provider,
                            stream=True, 
                            timeout=12, # Slightly more time for stability
                            web_search=web_search
                        )
                        
                        first = True
                        has_content = False
                        for chunk in response:
                            if hasattr(chunk.choices[0], 'delta') and hasattr(chunk.choices[0].delta, 'content'):
                                content = chunk.choices[0].delta.content
                                if content:
                                    if first: 
                                        logger.info(f"Priority Layer SUCCESS: {p_name} with {target_model}")
                                        first = False
                                    asyncio.run_coroutine_threadsafe(queue.put(content), loop)
                                    has_content = True
                        
                        if has_content:
                            asyncio.run_coroutine_threadsafe(queue.put(None), loop)
                            return
                    except Exception as pe:
                        # Detailed error logging
                        pe_str = str(pe).lower()
                        logger.debug(f"Priority Layer Error: {p_name} - {target_model}: {pe}")
                        
                        # If a provider explicitly asks for an API key, we should log it but skip it immediately
                        if any(x in pe_str for x in ["api_key", "api key", "auth", "token", "unauthorized"]):
                            logger.warning(f"Provider {p_name} requested API key or auth. Skipping.")
                            break # Try next provider
                        
                        # If the model is not supported, try the next model
                        if "model does not exist" in pe_str or "not supported" in pe_str:
                            continue
                            
                        # If the provider is completely down/not working, try next model or provider
                        continue

            # 3. Deep Fallback Loop (STABLE_PROVIDERS - Cleaned list)
            import random
            shuffled_providers = STABLE_PROVIDERS.copy()
            random.shuffle(shuffled_providers)
            
            fallback_models = ["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo", "llama-3.1-8b"]
            for provider_name in shuffled_providers:
                if provider_name in priority_providers: continue 
                
                breaker = get_breaker(provider_name)
                if not breaker.can_execute(): continue
                
                provider = getattr(g4f.Provider, provider_name, None)
                if not provider: continue

                for f_model in fallback_models:
                    try:
                        logger.info(f"Deep Fallback Layer: Provider={provider_name}, Model={f_model}")
                        response = client.chat.completions.create(
                            model=f_model, messages=messages, provider=provider,
                            stream=True, timeout=10, web_search=web_search
                        )
                        
                        first = True
                        has_content = False
                        for chunk in response:
                            if hasattr(chunk.choices[0], 'delta') and hasattr(chunk.choices[0].delta, 'content'):
                                content = chunk.choices[0].delta.content
                                if content:
                                    if first: 
                                        breaker.record_success()
                                        logger.info(f"Deep Fallback SUCCESS: {provider_name}")
                                        first = False
                                    asyncio.run_coroutine_threadsafe(queue.put(content), loop)
                                    has_content = True
                        
                        if has_content:
                            asyncio.run_coroutine_threadsafe(queue.put(None), loop)
                            return
                    except Exception as prov_e:
                        breaker.record_failure()
                        prov_e_str = str(prov_e).lower()
                        logger.debug(f"Deep Fallback Error: {provider_name}: {prov_e}")
                        if any(x in prov_e_str for x in ["api_key", "api key", "auth", "token", "unauthorized"]):
                            break # Skip this provider
                        if "model does not exist" in prov_e_str:
                            continue # Try next model
                        break 
            
            # 4. Final Rescue: Last-ditch attempt with known working pairs
            rescue_pairs = [
                ("gpt-4o-mini", "ApiAirforce"),
                ("gpt-4o", "PollinationsAI"),
                ("gpt-4o", "GlhfChat"),
                ("gpt-4o", "Blackbox")
            ]
            for r_model, r_provider_name in rescue_pairs:
                try:
                    logger.warning(f"Rescue Layer: Attempting {r_provider_name} with {r_model}")
                    r_provider = getattr(g4f.Provider, r_provider_name, None)
                    if not r_provider: continue
                    
                    response = client.chat.completions.create(
                        model=r_model, messages=messages, provider=r_provider,
                        stream=True, timeout=15
                    )
                    has_content = False
                    for chunk in response:
                        if hasattr(chunk.choices[0], 'delta') and hasattr(chunk.choices[0].delta, 'content'):
                            content = chunk.choices[0].delta.content
                            if content:
                                if not has_content: has_content = True
                                asyncio.run_coroutine_threadsafe(queue.put(content), loop)
                    if has_content:
                        asyncio.run_coroutine_threadsafe(queue.put(None), loop)
                        return
                except Exception as ree:
                    logger.debug(f"Rescue Layer Error: {r_provider_name}: {ree}")
                    continue

            error_msg = "DUB5 ervaart momenteel een verbindingsstoring. Probeer het over enkele seconden opnieuw."
            asyncio.run_coroutine_threadsafe(queue.put(Exception(error_msg)), loop)
        except Exception as e:
            logger.error(f"Critical error in fetch_chunks: {e}")
            error_msg = f"DUB5 Systeemfout: {str(e)}"
            asyncio.run_coroutine_threadsafe(queue.put(Exception(error_msg)), loop)

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
                
                # Pas filtering toe op de buffer
                cleaned_buffer = clean_text(stream_buffer)
                
                # Sliding Window: We houden een 'lookahead' aan om te voorkomen dat we een 
                # watermerk doormidden snijden als het over meerdere chunks komt.
                lookahead = 150 # Genoeg voor de langste bekende watermerk
                if len(cleaned_buffer) > lookahead:
                    safe_to_send = cleaned_buffer[:-lookahead]
                    stream_buffer = cleaned_buffer[-lookahead:]
                    
                    if safe_to_send:
                        full_response_text += safe_to_send
                        yield f"data: {json.dumps({'content': safe_to_send})}\n\n"
                else:
                    stream_buffer = cleaned_buffer

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
    mode_prompt = THINKING_MODES[thinking_mode]["system_prompt"]
    personality_prompt = PERSONALITIES[personality]["system_prompt"]
    
    # Log analytics
    input_tokens = count_tokens(user_input.input, model)
    analytics.log_request(model, input_tokens)

    # Gebruik custom system prompt als die is meegegeven, anders de standaard
    if user_input.custom_system_prompt:
        base_prompt = user_input.custom_system_prompt
    else:
        base_prompt = SYSTEM_PROMPT

    combined_system_prompt = f"{base_prompt}\n\nROL: {personality.upper()}\n{personality_prompt}\n\nMODUS: {thinking_mode.upper()}\n{mode_prompt}"
    
    if user_input.web_search:
        combined_system_prompt += "\n\nWEB SEARCH ENABLED: You have access to real-time information via web search. Use this capability to provide up-to-date information if the user asks for news, current events, or data beyond your training cutoff."

    try:
        # Build messages with history (memory)
        messages = [{"role": "system", "content": combined_system_prompt}]
        
        # Voeg history toe van de frontend
        if user_input.history:
            for msg in user_input.history:
                messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
        
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
            stream_chat_completion(messages, model, user_input.web_search, personality, user_input.image),
            media_type="text/event-stream",
            headers={
                "Content-Type": "text/event-stream",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
                "Transfer-Encoding": "chunked"
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

@app.get("/health")
async def health_check():
    # Basis health check voor de backend
    return {
        "status": "ok",
        "timestamp": time.time(),
        "version": "1.0.0",
        "providers": len(STABLE_PROVIDERS)
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
