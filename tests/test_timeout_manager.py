"""
Unit tests for the timeout_manager module.

Tests verify:
- Immediate heartbeat on stream start
- Periodic heartbeats during streaming
- Timeout enforcement at max_duration
- Graceful stream termination with duration tracking
"""

import asyncio
import json
import pytest
import time
from api.timeout_manager import with_timeout_protection, send_heartbeat


class TestSendHeartbeat:
    """Tests for the send_heartbeat function."""
    
    @pytest.mark.anyio
    async def test_send_heartbeat_format(self):
        """Test that send_heartbeat returns correct SSE format."""
        heartbeat = await send_heartbeat()
        assert heartbeat == ": heartbeat\n\n"
        assert heartbeat.startswith(":")
        assert heartbeat.endswith("\n\n")


class TestWithTimeoutProtection:
    """Tests for the with_timeout_protection function."""
    
    @pytest.mark.anyio
    async def test_immediate_heartbeat(self):
        """Test that first message is an immediate heartbeat."""
        async def simple_generator():
            yield "data: test\n\n"
        
        chunks = []
        async for chunk in with_timeout_protection(simple_generator()):
            chunks.append(chunk)
        
        # First chunk should be a heartbeat
        assert chunks[0] == ": heartbeat\n\n"
    
    @pytest.mark.anyio
    async def test_yields_generator_chunks(self):
        """Test that chunks from the generator are yielded."""
        async def simple_generator():
            yield "data: chunk1\n\n"
            yield "data: chunk2\n\n"
        
        chunks = []
        async for chunk in with_timeout_protection(simple_generator()):
            chunks.append(chunk)
        
        # Should have: heartbeat, chunk1, chunk2, end message
        assert len(chunks) >= 3
        assert "data: chunk1\n\n" in chunks
        assert "data: chunk2\n\n" in chunks
    
    @pytest.mark.anyio
    async def test_end_message_with_duration(self):
        """Test that stream ends with duration information."""
        async def simple_generator():
            yield "data: test\n\n"
        
        chunks = []
        async for chunk in with_timeout_protection(simple_generator()):
            chunks.append(chunk)
        
        # Last chunk should be end message with duration
        last_chunk = chunks[-1]
        assert last_chunk.startswith("data: ")
        
        # Parse the JSON to verify structure
        json_str = last_chunk.replace("data: ", "").strip()
        data = json.loads(json_str)
        assert data["type"] == "end"
        assert "duration" in data
        assert isinstance(data["duration"], (int, float))
        assert data["duration"] >= 0
    
    @pytest.mark.anyio
    async def test_timeout_enforcement(self):
        """Test that stream times out after max_duration."""
        async def slow_generator():
            for i in range(100):
                yield f"data: chunk{i}\n\n"
                await asyncio.sleep(0.2)  # 20 seconds total
        
        chunks = []
        start_time = time.time()
        
        # Set max_duration to 1 second for faster test
        async for chunk in with_timeout_protection(slow_generator(), max_duration=1):
            chunks.append(chunk)
        
        elapsed = time.time() - start_time
        
        # Should timeout around 1 second (with some tolerance)
        assert elapsed < 2.0, "Stream should have timed out"
        
        # Should have a timeout message
        timeout_found = False
        for chunk in chunks:
            if "timeout" in chunk.lower():
                data = json.loads(chunk.replace("data: ", "").strip())
                if data.get("type") == "timeout":
                    timeout_found = True
                    assert "elapsed" in data
                    break
        
        assert timeout_found, "Should have received timeout message"
    
    @pytest.mark.anyio
    async def test_periodic_heartbeats(self):
        """Test that heartbeats are sent periodically."""
        async def slow_generator():
            for i in range(3):
                await asyncio.sleep(0.3)
                yield f"data: chunk{i}\n\n"
        
        chunks = []
        # Set heartbeat_interval to 0.2 seconds for faster test
        async for chunk in with_timeout_protection(
            slow_generator(), 
            max_duration=10, 
            heartbeat_interval=0.2
        ):
            chunks.append(chunk)
        
        # Count heartbeats (excluding the immediate one)
        heartbeat_count = sum(1 for chunk in chunks if chunk == ": heartbeat\n\n")
        
        # Should have at least 2 heartbeats (immediate + periodic)
        assert heartbeat_count >= 2, f"Expected at least 2 heartbeats, got {heartbeat_count}"
    
    @pytest.mark.anyio
    async def test_empty_generator(self):
        """Test handling of empty generator."""
        async def empty_generator():
            return
            yield  # Make it a generator
        
        chunks = []
        async for chunk in with_timeout_protection(empty_generator()):
            chunks.append(chunk)
        
        # Should have at least heartbeat and end message
        assert len(chunks) >= 2
        assert chunks[0] == ": heartbeat\n\n"
        
        # Last should be end message
        last_chunk = chunks[-1]
        data = json.loads(last_chunk.replace("data: ", "").strip())
        assert data["type"] == "end"
    
    @pytest.mark.anyio
    async def test_asyncio_timeout_error(self):
        """Test handling of asyncio.TimeoutError."""
        async def timeout_generator():
            raise asyncio.TimeoutError("Test timeout")
            yield  # Make it a generator
        
        chunks = []
        async for chunk in with_timeout_protection(timeout_generator()):
            chunks.append(chunk)
        
        # Should have heartbeat, timeout message, and end message
        assert len(chunks) >= 2
        
        # Should have a timeout message
        timeout_found = False
        for chunk in chunks:
            if "data:" in chunk and "timeout" in chunk.lower():
                data = json.loads(chunk.replace("data: ", "").strip())
                if data.get("type") == "timeout" and data.get("content") == "Stream timeout":
                    timeout_found = True
                    break
        
        assert timeout_found, "Should have received timeout error message"
