"""
Unit tests for the error_handler module.
"""

import pytest
import json
from datetime import datetime
from api.error_handler import (
    ServerlessError,
    ImportFailureError,
    TimeoutError,
    handle_import_error,
    handle_ai_provider_error,
    log_error,
    create_error_response
)


class TestCustomExceptions:
    """Test suite for custom exception classes."""
    
    def test_serverless_error_is_exception(self):
        """Test that ServerlessError is an Exception subclass."""
        error = ServerlessError("Test error")
        assert isinstance(error, Exception)
        assert str(error) == "Test error"
    
    def test_import_failure_error_is_serverless_error(self):
        """Test that ImportFailureError is a ServerlessError subclass."""
        error = ImportFailureError("Import failed")
        assert isinstance(error, ServerlessError)
        assert isinstance(error, Exception)
        assert str(error) == "Import failed"
    
    def test_timeout_error_is_serverless_error(self):
        """Test that TimeoutError is a ServerlessError subclass."""
        error = TimeoutError("Operation timed out")
        assert isinstance(error, ServerlessError)
        assert isinstance(error, Exception)
        assert str(error) == "Operation timed out"


class TestHandleImportError:
    """Test suite for handle_import_error function."""
    
    def test_handle_import_error_logs_without_raising(self, caplog):
        """Test that handle_import_error logs the error without raising an exception."""
        test_error = ImportError("Module not found")
        
        # Should not raise an exception
        handle_import_error("test_module", test_error)
        
        # Should log the error
        assert len(caplog.records) > 0
        log_record = caplog.records[0]
        assert log_record.levelname == "ERROR"
        
        # Parse the JSON log message
        log_data = json.loads(log_record.message)
        assert log_data["error_type"] == "import"
        assert "test_module" in log_data["message"]
        assert log_data["context"]["module_name"] == "test_module"
        assert log_data["exception"] == "Module not found"
        assert log_data["exception_type"] == "ImportError"


class TestHandleAIProviderError:
    """Test suite for handle_ai_provider_error function."""
    
    def test_handle_ai_provider_error_returns_structured_response(self):
        """Test that handle_ai_provider_error returns a properly structured error response."""
        test_error = Exception("Connection timeout")
        
        response = handle_ai_provider_error("g4f", test_error)
        
        # Verify response structure
        assert response["type"] == "error"
        assert response["error_code"] == "PROVIDER_FAILURE"
        assert "g4f" in response["message"]
        assert "temporarily unavailable" in response["message"]
        assert "g4f provider failed: Connection timeout" in response["details"]
        assert "timestamp" in response
        assert response["retry_after"] == 60
        
        # Verify timestamp format (ISO 8601 with Z suffix)
        timestamp = response["timestamp"]
        assert timestamp.endswith("Z")
        # Should be parseable as ISO format
        datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    
    def test_handle_ai_provider_error_logs_error(self, caplog):
        """Test that handle_ai_provider_error logs the error."""
        test_error = Exception("API rate limit exceeded")
        
        handle_ai_provider_error("pollinations", test_error)
        
        # Should log the error
        assert len(caplog.records) > 0
        log_record = caplog.records[0]
        assert log_record.levelname == "ERROR"
        
        # Parse the JSON log message
        log_data = json.loads(log_record.message)
        assert log_data["error_type"] == "provider"
        assert "pollinations" in log_data["message"]
        assert log_data["context"]["provider"] == "pollinations"


class TestLogError:
    """Test suite for log_error function."""
    
    def test_log_error_basic(self, caplog):
        """Test basic error logging without exception or context."""
        log_error(
            error_type="test",
            message="Test error message"
        )
        
        assert len(caplog.records) > 0
        log_record = caplog.records[0]
        assert log_record.levelname == "ERROR"
        
        log_data = json.loads(log_record.message)
        assert log_data["error_type"] == "test"
        assert log_data["message"] == "Test error message"
        assert log_data["context"] == {}
        assert "exception" not in log_data
    
    def test_log_error_with_exception(self, caplog):
        """Test error logging with exception."""
        test_exception = ValueError("Invalid value")
        
        log_error(
            error_type="validation",
            message="Validation failed",
            exception=test_exception
        )
        
        log_record = caplog.records[0]
        log_data = json.loads(log_record.message)
        
        assert log_data["exception"] == "Invalid value"
        assert log_data["exception_type"] == "ValueError"
    
    def test_log_error_with_context(self, caplog):
        """Test error logging with additional context."""
        context = {
            "user_id": "user123",
            "request_id": "req456",
            "operation": "file_read"
        }
        
        log_error(
            error_type="file",
            message="File operation failed",
            context=context
        )
        
        log_record = caplog.records[0]
        log_data = json.loads(log_record.message)
        
        assert log_data["context"] == context
        assert log_data["context"]["user_id"] == "user123"
        assert log_data["context"]["request_id"] == "req456"


class TestCreateErrorResponse:
    """Test suite for create_error_response function."""
    
    def test_create_error_response_minimal(self):
        """Test creating error response with minimal parameters."""
        response = create_error_response(
            error_code="TEST_ERROR",
            message="Test error occurred"
        )
        
        assert response["type"] == "error"
        assert response["error_code"] == "TEST_ERROR"
        assert response["message"] == "Test error occurred"
        assert "timestamp" in response
        assert "details" not in response
        assert "retry_after" not in response
        
        # Verify timestamp format
        timestamp = response["timestamp"]
        assert timestamp.endswith("Z")
        datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    
    def test_create_error_response_with_details(self):
        """Test creating error response with details."""
        response = create_error_response(
            error_code="FILE_NOT_FOUND",
            message="File not found",
            details="The file config.json does not exist in the current directory"
        )
        
        assert response["details"] == "The file config.json does not exist in the current directory"
    
    def test_create_error_response_with_retry_after(self):
        """Test creating error response with retry_after."""
        response = create_error_response(
            error_code="RATE_LIMIT",
            message="Rate limit exceeded",
            retry_after=120
        )
        
        assert response["retry_after"] == 120
    
    def test_create_error_response_complete(self):
        """Test creating error response with all parameters."""
        response = create_error_response(
            error_code="PROVIDER_TIMEOUT",
            message="Provider request timed out",
            details="The AI provider did not respond within 50 seconds",
            retry_after=60
        )
        
        assert response["type"] == "error"
        assert response["error_code"] == "PROVIDER_TIMEOUT"
        assert response["message"] == "Provider request timed out"
        assert response["details"] == "The AI provider did not respond within 50 seconds"
        assert response["retry_after"] == 60
        assert "timestamp" in response
