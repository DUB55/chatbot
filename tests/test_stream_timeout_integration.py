"""
Integration tests for timeout wrapper in stream_chat_completion.

This test verifies that the timeout wrapper is properly integrated
with the stream_chat_completion function.
"""

import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.anyio
async def test_stream_chat_completion_uses_timeout_wrapper():
    """
    Test that stream_chat_completion properly wraps the generator with timeout protection.
    
    This test verifies:
    1. The timeout wrapper is applied to the streaming generator
    2. Heartbeat messages are sent
    3. Timeout and end messages are properly formatted
    """
    from api import chatbot_backup
    
    # Mock messages
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello"}
    ]
    
    # Mock the fetch_chunks_async to return a simple generator
    async def mock_fetch_chunks(*args, **kwargs):
        yield "Hello"
        yield " world"
        yield None  # Sentinel value
    
    # Patch at the module level where it's used
    original_fetch = chatbot_backup.fetch_chunks_async
    chatbot_backup.fetch_chunks_async = mock_fetch_chunks
    
    try:
        with patch('api.chatbot_backup.chat_cache') as mock_cache:
            # Make sure cache returns None so we don't use cached response
            mock_cache.get.return_value = None
            with patch('api.chatbot_backup.analytics') as mock_analytics:
                with patch('api.chatbot_backup.count_tokens', return_value=10):
                    chunks = []
                    async for chunk in chatbot_backup.stream_chat_completion(
                        messages=messages,
                        model="gpt-4o",
                        web_search=False,
                        personality_name="general",
                        image_data=None,
                        force_roulette=False,
                        session_id="test_session"
                    ):
                        chunks.append(chunk)
    finally:
        # Restore original function
        chatbot_backup.fetch_chunks_async = original_fetch
    
    # Verify we got chunks
    assert len(chunks) > 0, f"Expected chunks but got {len(chunks)}"
    
    # Debug: print chunks to see what we got
    print(f"\nReceived {len(chunks)} chunks:")
    for i, chunk in enumerate(chunks):
        print(f"  {i}: {chunk[:100] if len(chunk) > 100 else chunk}")
    
    # Verify we got a heartbeat (from timeout wrapper)
    heartbeat_found = any(": heartbeat" in chunk for chunk in chunks)
    assert heartbeat_found, f"Expected heartbeat message from timeout wrapper. Got chunks: {chunks}"
    
    # Verify we got metadata
    metadata_found = any("metadata" in chunk for chunk in chunks)
    assert metadata_found, "Expected metadata message"
    
    # Verify we got an end message (from timeout wrapper)
    end_found = any("end" in chunk and "duration" in chunk for chunk in chunks)
    assert end_found, "Expected end message with duration from timeout wrapper"


@pytest.mark.anyio
async def test_g4f_client_configured_with_timeout():
    """
    Test that g4f client is configured with 50-second timeout.
    
    This test verifies that when creating a g4f client, it's configured
    with the appropriate timeout value.
    """
    from api.chatbot_backup import fetch_chunks_async
    
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello"}
    ]
    
    # Mock the g4f provider selection
    mock_provider = MagicMock()
    mock_provider.__name__ = "MockProvider"
    
    with patch('api.chatbot_backup.get_best_g4f_provider', return_value=mock_provider):
        # Mock the lazy import function to return mocked g4f
        mock_g4f_module = MagicMock()
        mock_client_class = MagicMock()
        
        with patch('api.chatbot_backup._lazy_import_g4f', return_value=(mock_g4f_module, mock_client_class, True)):
            # Create a mock client instance
            mock_client_instance = MagicMock()
            mock_client_class.return_value = mock_client_instance
            
            # Mock the chat completions to raise an exception (so we don't actually call the API)
            mock_client_instance.chat.completions.create = AsyncMock(
                side_effect=Exception("Test exception")
            )
            
            # Call fetch_chunks_async
            chunks = []
            try:
                async for chunk in fetch_chunks_async(
                    messages=messages,
                    model="gpt-4o",
                    web_search=False,
                    personality_name="general",
                    image_data=None,
                    force_roulette=False,
                    session_id="test_session"
                ):
                    chunks.append(chunk)
                    if isinstance(chunk, Exception):
                        break
            except Exception:
                pass
            
            # Verify that Client was called with timeout=50
            mock_client_class.assert_called_with(provider=mock_provider, timeout=50)


@pytest.mark.anyio
async def test_pollinations_client_configured_with_timeout():
    """
    Test that Pollinations httpx client is configured with 50-second timeout.
    
    This test verifies that when making Pollinations API calls, the httpx
    client is configured with the appropriate timeout value.
    """
    from api.chatbot_backup import fetch_chunks_async
    import httpx
    
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello"}
    ]
    
    # Mock g4f to fail so we fall back to Pollinations
    with patch('api.chatbot_backup.get_best_g4f_provider', return_value=None):
        with patch('httpx.AsyncClient') as mock_async_client:
            # Create a mock context manager
            mock_client_instance = MagicMock()
            mock_stream_response = MagicMock()
            mock_stream_response.is_success = False
            mock_stream_response.status_code = 500
            mock_stream_response.aread = AsyncMock(return_value=b"Error")
            
            mock_client_instance.stream = MagicMock()
            mock_client_instance.stream.return_value.__aenter__ = AsyncMock(
                return_value=mock_stream_response
            )
            mock_client_instance.stream.return_value.__aexit__ = AsyncMock(return_value=None)
            
            mock_async_client.return_value.__aenter__ = AsyncMock(
                return_value=mock_client_instance
            )
            mock_async_client.return_value.__aexit__ = AsyncMock(return_value=None)
            
            # Call fetch_chunks_async
            chunks = []
            try:
                async for chunk in fetch_chunks_async(
                    messages=messages,
                    model="gpt-4o",
                    web_search=False,
                    personality_name="general",
                    image_data=None,
                    force_roulette=False,
                    session_id="test_session"
                ):
                    chunks.append(chunk)
                    if isinstance(chunk, Exception):
                        break
            except Exception:
                pass
            
            # Verify that AsyncClient was called with timeout=50.0
            mock_async_client.assert_called_with(timeout=50.0)
