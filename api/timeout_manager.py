"""
Timeout Management Module

This module provides timeout protection for async generators to ensure
AI streaming requests complete within Vercel's 60-second serverless limit.

Key features:
- Immediate heartbeat on stream start to prevent timeout
- Periodic heartbeats every 10 seconds during streaming
- Timeout enforcement at 50 seconds (10 second buffer before Vercel's 60s limit)
- Graceful stream termination with duration tracking
"""

import asyncio
import json
import time
from typing import AsyncGenerator


async def with_timeout_protection(
    generator: AsyncGenerator,
    max_duration: int = 50,
    heartbeat_interval: int = 10
) -> AsyncGenerator:
    """
    Wraps an async generator with timeout and heartbeat management.
    
    This function ensures that streaming responses complete within Vercel's
    serverless function timeout limit by:
    1. Sending an immediate heartbeat to prevent early timeout
    2. Sending periodic heartbeats every 10 seconds to keep connection alive
    3. Enforcing a maximum duration of 50 seconds (with 10s buffer)
    4. Gracefully terminating the stream with duration information
    
    Args:
        generator: Source async generator that yields SSE-formatted chunks
        max_duration: Maximum duration in seconds before forced termination (default: 50)
        heartbeat_interval: Interval in seconds between heartbeat messages (default: 10)
        
    Yields:
        str: SSE-formatted chunks from the generator, heartbeat messages, or timeout messages
        
    Example:
        >>> async def my_stream():
        ...     yield "data: chunk1\\n\\n"
        ...     yield "data: chunk2\\n\\n"
        >>> 
        >>> async for chunk in with_timeout_protection(my_stream()):
        ...     print(chunk)
    """
    start_time = time.time()
    last_heartbeat = start_time
    
    # Send immediate heartbeat to prevent Vercel timeout
    yield ": heartbeat\n\n"
    
    try:
        async for chunk in generator:
            current_time = time.time()
            elapsed = current_time - start_time
            
            # Check if we've exceeded the maximum duration
            if elapsed > max_duration:
                yield f"data: {json.dumps({
                    'type': 'timeout',
                    'content': 'Request exceeded time limit',
                    'elapsed': elapsed
                })}\n\n"
                break
            
            # Send periodic heartbeat to keep connection alive
            if current_time - last_heartbeat > heartbeat_interval:
                yield ": heartbeat\n\n"
                last_heartbeat = current_time
            
            # Yield the actual chunk from the generator
            yield chunk
            
    except asyncio.TimeoutError:
        # Handle asyncio timeout errors
        yield f"data: {json.dumps({
            'type': 'timeout',
            'content': 'Stream timeout'
        })}\n\n"
    finally:
        # Always send end message with duration information
        end_time = time.time()
        duration = end_time - start_time
        yield f"data: {json.dumps({
            'type': 'end',
            'duration': duration
        })}\n\n"


async def send_heartbeat() -> str:
    """
    Generates an SSE heartbeat message.
    
    Heartbeat messages are SSE comments (lines starting with ':') that
    keep the connection alive without sending data to the client.
    
    Returns:
        str: SSE-formatted heartbeat message
        
    Example:
        >>> heartbeat = await send_heartbeat()
        >>> print(heartbeat)
        : heartbeat
        
    """
    return ": heartbeat\n\n"
