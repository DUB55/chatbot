import os
import json
import sys
import httpx
import random
import time
import asyncio
import logging
from typing import Optional, List, Dict, Any, AsyncGenerator
from tenacity import retry, wait_exponential, stop_after_attempt

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Simple g4f mock for Vercel stability
class MockG4FClient:
    def __init__(self, provider=None):
        self.provider = provider
    
    class chat:
        class completions:
            @staticmethod
            async def create(model, messages, stream=True):
                # Mock response - always fail to force Pollinations fallback
                raise Exception("g4f mock - forcing Pollinations fallback")
        completions = completions()
    chat = chat()

# Try to import real g4f, but use mock if it fails
try:
    import g4f
    from g4f.client import Client
    logger.info("Real g4f imported successfully")
except Exception as e:
    logger.warning(f"Failed to import g4f, using mock: {e}")
    g4f = None
    Client = MockG4FClient

# Simple provider list for Vercel
G4F_PROVIDERS = []

def get_best_g4f_provider():
    """Get best available g4f provider - simplified for Vercel"""
    return None  # Always use Pollinations for stability

# Simple text cleaning
def clean_text(text):
    """Clean text response"""
    if not text:
        return ""
    return text.strip()

# Main streaming function
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
    
    # Metadata event
    yield f"data: {json.dumps({'type': 'metadata', 'model': model, 'personality': personality_name, 'session_id': session_id})}\n\n"
    
    # Heartbeat to prevent Vercel timeout
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
            if chunk is None:
                break
            if isinstance(chunk, Exception):
                raise chunk
            
            cleaned_chunk = clean_text(chunk) if chunk else ""
            if cleaned_chunk:
                yield f"data: {json.dumps({'type': 'chunk', 'content': cleaned_chunk})}\n\n"
                full_response_text += cleaned_chunk
                
    except Exception as e:
        logger.error(f"Error during chat streaming for session_id: {session_id}: {e}")
        yield f"data: {json.dumps({'type': 'error', 'content': f'Error during streaming: {e}'})}\n\n"
    finally:
        logger.info(f"Stream finished for session_id: {session_id}. Total response length: {len(full_response_text)}")
        
        end_time = time.time()
        duration = end_time - start_time
        
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
        # Skip g4f for now - go directly to Pollinations for stability
        logger.info(f"Using Pollinations AI for session_id: {session_id}")
        
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
        
        # Add timeout and error handling
        timeout = httpx.Timeout(60.0, connect=10.0)
        
        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
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
                        logger.error(f"Pollinations AI failed with status {response.status_code}: {response.body.decode()}")
                        raise Exception(f"Pollinations AI HTTP error: {response.status_code}")

            except httpx.TimeoutException:
                logger.error("Pollinations AI request timed out")
                raise Exception("Pollinations AI request timed out")
            except httpx.ConnectError:
                logger.error("Pollinations AI connection failed")
                raise Exception("Pollinations AI connection failed")
            except Exception as e:
                logger.error(f"Pollinations AI request failed: {e}")
                raise

        end_time_pollinations = time.perf_counter()
        duration_pollinations = end_time_pollinations - start_time_pollinations
        logger.info(f"Pollinations AI call completed in {duration_pollinations:.4f} seconds.")
        yield None  # Signal end of stream
        return
        
    except Exception as e:
        logger.error(f"Error in fetch_chunks_async for session_id: {session_id}: {e}")
        yield Exception(f"Streaming error: {e}")
