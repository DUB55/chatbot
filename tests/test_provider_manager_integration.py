"""
Integration tests for ProviderManager in stream_chat_completion.

This test verifies that the ProviderManager is properly integrated
with the fetch_chunks_async function for automatic provider fallback.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.anyio
async def test_fetch_chunks_uses_provider_manager():
    """
    Test that fetch_chunks_async uses ProviderManager for provider selection.
    
    This test verifies:
    1. ProviderManager is instantiated
    2. get_next_provider() is called to select providers
    3. Failures are recorded with record_failure()
    4. Successes are recorded with record_success()
    """
    from api.chatbot_backup import fetch_chunks_async
    
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello"}
    ]
    
    # Mock the ProviderManager
    with patch('api.chatbot_backup.ProviderManager') as mock_pm_class:
        mock_pm_instance = MagicMock()
        mock_pm_class.return_value = mock_pm_instance
        
        # First call returns "g4f", second call returns "pollinations"
        mock_pm_instance.get_next_provider.side_effect = ["g4f", "pollinations"]
        
        # Mock g4f to fail
        mock_provider = MagicMock()
        mock_provider.__name__ = "MockProvider"
        
        # Mock the lazy import function to return mocked g4f
        mock_g4f_module = MagicMock()
        mock_client_class = MagicMock()
        
        with patch('api.chatbot_backup._lazy_import_g4f', return_value=(mock_g4f_module, mock_client_class, True)):
            with patch('api.chatbot_backup.get_best_g4f_provider', return_value=mock_provider):
                mock_client_instance = MagicMock()
                mock_client_class.return_value = mock_client_instance
                
                # Make g4f fail
                mock_client_instance.chat.completions.create = AsyncMock(
                    side_effect=Exception("g4f failed")
                )
                
                # Mock Pollinations to succeed
                with patch('httpx.AsyncClient') as mock_async_client:
                    mock_client_http = MagicMock()
                    mock_stream_response = MagicMock()
                    mock_stream_response.is_success = True
                    mock_stream_response.status_code = 200
                    
                    # Mock the streaming response
                    async def mock_aiter_bytes():
                        yield b'data: {"choices":[{"delta":{"content":"Hello"}}]}\n'
                        yield b'data: [DONE]\n'
                    
                    mock_stream_response.aiter_bytes = mock_aiter_bytes
                    
                    mock_client_http.stream = MagicMock()
                    mock_client_http.stream.return_value.__aenter__ = AsyncMock(
                        return_value=mock_stream_response
                    )
                    mock_client_http.stream.return_value.__aexit__ = AsyncMock(return_value=None)
                    
                    mock_async_client.return_value.__aenter__ = AsyncMock(
                        return_value=mock_client_http
                    )
                    mock_async_client.return_value.__aexit__ = AsyncMock(return_value=None)
                    
                    # Call fetch_chunks_async
                    chunks = []
                    async for chunk in fetch_chunks_async(
                        messages=messages,
                        model="gpt-4o",
                        web_search=False,
                        personality_name="general",
                        image_data=None,
                        force_roulette=False,
                        session_id="test_session"
                    ):
                        if chunk is not None and not isinstance(chunk, Exception):
                            chunks.append(chunk)
        
        # Verify ProviderManager was instantiated with correct providers
        mock_pm_class.assert_called_once_with(providers=["g4f", "pollinations"])
        
        # Verify get_next_provider was called (at least once for g4f, possibly twice for fallback)
        assert mock_pm_instance.get_next_provider.call_count >= 1
        
        # Verify record_failure was called for g4f
        mock_pm_instance.record_failure.assert_called_with("g4f")
        
        # Verify record_success was called for pollinations
        mock_pm_instance.record_success.assert_called_with("pollinations")


@pytest.mark.anyio
async def test_all_providers_fail_returns_error():
    """
    Test that when all providers fail, an appropriate error is returned.
    
    This test verifies:
    1. Both g4f and pollinations are attempted
    2. Failures are recorded for both providers
    3. An error message is yielded when all providers fail
    """
    from api.chatbot_backup import fetch_chunks_async
    
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello"}
    ]
    
    # Mock the ProviderManager
    with patch('api.chatbot_backup.ProviderManager') as mock_pm_class:
        mock_pm_instance = MagicMock()
        mock_pm_class.return_value = mock_pm_instance
        
        # Return providers in order
        mock_pm_instance.get_next_provider.side_effect = ["g4f", "pollinations"]
        
        # Mock g4f to fail
        mock_provider = MagicMock()
        mock_provider.__name__ = "MockProvider"
        
        with patch('api.chatbot_backup.get_best_g4f_provider', return_value=mock_provider):
            # Mock the lazy import function to return mocked g4f
            mock_g4f_module = MagicMock()
            mock_client_class = MagicMock()
            
            with patch('api.chatbot_backup._lazy_import_g4f', return_value=(mock_g4f_module, mock_client_class, True)):
                mock_client_instance = MagicMock()
                mock_client_class.return_value = mock_client_instance
                
                # Make g4f fail
                mock_client_instance.chat.completions.create = AsyncMock(
                    side_effect=Exception("g4f failed")
                )
                
                # Mock Pollinations to also fail
                with patch('httpx.AsyncClient') as mock_async_client:
                    mock_client_http = MagicMock()
                    mock_stream_response = MagicMock()
                    mock_stream_response.is_success = False
                    mock_stream_response.status_code = 500
                    mock_stream_response.aread = AsyncMock(return_value=b"Pollinations error")
                    
                    mock_client_http.stream = MagicMock()
                    mock_client_http.stream.return_value.__aenter__ = AsyncMock(
                        return_value=mock_stream_response
                    )
                    mock_client_http.stream.return_value.__aexit__ = AsyncMock(return_value=None)
                    
                    mock_async_client.return_value.__aenter__ = AsyncMock(
                        return_value=mock_client_http
                    )
                    mock_async_client.return_value.__aexit__ = AsyncMock(return_value=None)
                    
                    # Call fetch_chunks_async
                    chunks = []
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
        
        # Verify both providers were tried
        assert mock_pm_instance.get_next_provider.call_count == 2
        
        # Verify failures were recorded for both providers
        assert mock_pm_instance.record_failure.call_count == 2
        
        # Verify we got an error message
        assert len(chunks) > 0
        error_found = any(isinstance(chunk, Exception) for chunk in chunks)
        assert error_found, "Expected an Exception to be yielded when all providers fail"
        
        # Verify the error message mentions all providers unavailable
        error_chunk = next(chunk for chunk in chunks if isinstance(chunk, Exception))
        assert "All AI providers unavailable" in str(error_chunk)


@pytest.mark.anyio
async def test_g4f_success_records_success():
    """
    Test that successful g4f calls record success with ProviderManager.
    
    This test verifies:
    1. g4f provider is selected
    2. g4f succeeds
    3. record_success is called for g4f
    """
    from api.chatbot_backup import fetch_chunks_async
    
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello"}
    ]
    
    # Mock the ProviderManager
    with patch('api.chatbot_backup.ProviderManager') as mock_pm_class:
        mock_pm_instance = MagicMock()
        mock_pm_class.return_value = mock_pm_instance
        
        # Return g4f as the provider
        mock_pm_instance.get_next_provider.return_value = "g4f"
        
        # Mock g4f to succeed
        mock_provider = MagicMock()
        mock_provider.__name__ = "MockProvider"
        
        with patch('api.chatbot_backup.get_best_g4f_provider', return_value=mock_provider):
            # Mock the lazy import function to return mocked g4f
            mock_g4f_module = MagicMock()
            mock_client_class = MagicMock()
            
            with patch('api.chatbot_backup._lazy_import_g4f', return_value=(mock_g4f_module, mock_client_class, True)):
                mock_client_instance = MagicMock()
                mock_client_class.return_value = mock_client_instance
                
                # Create a mock response
                mock_chunk1 = MagicMock()
                mock_chunk1.choices = [MagicMock()]
                mock_chunk1.choices[0].delta.content = "Hello"
                
                mock_chunk2 = MagicMock()
                mock_chunk2.choices = [MagicMock()]
                mock_chunk2.choices[0].delta.content = " world"
                
                # Make g4f succeed
                mock_client_instance.chat.completions.create = AsyncMock(
                    return_value=[mock_chunk1, mock_chunk2]
                )
                
                # Mock g4f_provider_performance
                with patch('api.chatbot_backup.g4f_provider_performance', {"MockProvider": {
                    "success_count": 0,
                    "failure_count": 0,
                    "total_latency": 0.0,
                    "last_used_time": 0.0,
                    "last_failure_time": 0.0,
                    "consecutive_failures": 0
                }}):
                    # Call fetch_chunks_async
                    chunks = []
                    async for chunk in fetch_chunks_async(
                        messages=messages,
                        model="gpt-4o",
                        web_search=False,
                        personality_name="general",
                        image_data=None,
                        force_roulette=False,
                        session_id="test_session"
                    ):
                        if chunk is not None:
                            chunks.append(chunk)
        
        # Verify get_next_provider was called
        mock_pm_instance.get_next_provider.assert_called()
        
        # Verify record_success was called for g4f
        mock_pm_instance.record_success.assert_called_with("g4f")
        
        # Verify record_failure was NOT called
        mock_pm_instance.record_failure.assert_not_called()
