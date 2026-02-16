"""
Error Handling Module

This module provides comprehensive error handling for serverless constraints,
including custom exception classes, error handlers, and structured logging.

Key features:
- Custom exception classes for serverless-specific errors
- Structured error response generation
- Import failure handling with fallback logic
- AI provider error handling
- Structured logging for debugging
"""

import logging
import json
from typing import Optional, Dict, Any
from datetime import datetime, timezone


# Configure logger
logger = logging.getLogger(__name__)


# ============================================================================
# Custom Exception Classes
# ============================================================================

class ServerlessError(Exception):
    """
    Base exception for serverless-specific errors.
    
    This exception serves as the parent class for all serverless-related
    errors, allowing for broad exception handling when needed.
    """
    pass


class ImportFailureError(ServerlessError):
    """
    Raised when critical imports fail.
    
    This exception is raised when a required module cannot be imported,
    typically due to missing dependencies or import path issues in the
    serverless environment.
    """
    pass


class TimeoutError(ServerlessError):
    """
    Raised when operations exceed time limits.
    
    This exception is raised when an operation exceeds the maximum allowed
    duration, particularly important in Vercel's 60-second serverless limit.
    """
    pass


# ============================================================================
# Error Handling Functions
# ============================================================================

def handle_import_error(module_name: str, error: Exception) -> None:
    """
    Handles import failures with logging and fallback logic.
    
    This function logs detailed information about import failures to aid
    debugging in serverless environments where import issues are common.
    It does not raise an exception, allowing the application to continue
    with fallback implementations where possible.
    
    Args:
        module_name: Name of the module that failed to import
        error: The import exception that was raised
        
    Example:
        >>> try:
        ...     import some_module
        ... except ImportError as e:
        ...     handle_import_error("some_module", e)
    """
    log_error(
        error_type="import",
        message=f"Failed to import module: {module_name}",
        exception=error,
        context={
            "module_name": module_name,
            "error_type": type(error).__name__
        }
    )


def handle_ai_provider_error(provider: str, error: Exception) -> Dict[str, Any]:
    """
    Handles AI provider failures and returns structured error response.
    
    This function processes errors from AI providers (g4f, Pollinations AI)
    and returns a standardized error response that can be sent to clients.
    It also logs the error for debugging purposes.
    
    Args:
        provider: Name of the AI provider that failed (e.g., "g4f", "pollinations")
        error: The exception raised by the provider
        
    Returns:
        dict: Structured error response with type, error_code, message, details,
              timestamp, and retry_after fields
              
    Example:
        >>> try:
        ...     result = await call_ai_provider()
        ... except Exception as e:
        ...     error_response = handle_ai_provider_error("g4f", e)
        ...     return json.dumps(error_response)
    """
    # Log the error with context
    log_error(
        error_type="provider",
        message=f"AI provider '{provider}' failed",
        exception=error,
        context={
            "provider": provider,
            "error_type": type(error).__name__
        }
    )
    
    # Return structured error response
    return {
        "type": "error",
        "error_code": "PROVIDER_FAILURE",
        "message": f"AI provider '{provider}' is temporarily unavailable",
        "details": f"{provider} provider failed: {str(error)}",
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "retry_after": 60
    }


def log_error(
    error_type: str,
    message: str,
    exception: Optional[Exception] = None,
    context: Optional[Dict[str, Any]] = None
) -> None:
    """
    Logs errors with structured context for debugging.
    
    This function provides structured logging that includes error type,
    message, exception details, and additional context. The structured
    format makes it easier to parse logs in monitoring systems.
    
    Args:
        error_type: Category of error (import, file, provider, timeout, config)
        message: Human-readable error description
        exception: The exception object if available (optional)
        context: Additional context dictionary (request_id, user_id, etc.) (optional)
        
    Example:
        >>> log_error(
        ...     error_type="file",
        ...     message="Failed to read configuration file",
        ...     exception=FileNotFoundError("config.json not found"),
        ...     context={"file_path": "config.json", "operation": "read"}
        ... )
    """
    log_data = {
        "error_type": error_type,
        "message": message,
        "context": context or {}
    }
    
    if exception:
        log_data["exception"] = str(exception)
        log_data["exception_type"] = type(exception).__name__
    
    # Log as JSON for structured logging
    logger.error(json.dumps(log_data), exc_info=exception is not None)


# ============================================================================
# Error Response Generation
# ============================================================================

def create_error_response(
    error_code: str,
    message: str,
    details: Optional[str] = None,
    retry_after: Optional[int] = None
) -> Dict[str, Any]:
    """
    Creates a standardized error response structure.
    
    This function generates error responses that follow a consistent format
    across the application, making it easier for clients to handle errors.
    
    Args:
        error_code: Machine-readable error code (e.g., "IMPORT_FAILURE", "TIMEOUT")
        message: Human-readable error message
        details: Additional error details (optional)
        retry_after: Suggested retry delay in seconds (optional)
        
    Returns:
        dict: Structured error response with type, error_code, message, details,
              timestamp, and retry_after fields
              
    Example:
        >>> error = create_error_response(
        ...     error_code="FILE_NOT_FOUND",
        ...     message="Configuration file not found",
        ...     details="The file config.json does not exist",
        ...     retry_after=None
        ... )
    """
    response = {
        "type": "error",
        "error_code": error_code,
        "message": message,
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    }
    
    if details:
        response["details"] = details
    
    if retry_after is not None:
        response["retry_after"] = retry_after
    
    return response
