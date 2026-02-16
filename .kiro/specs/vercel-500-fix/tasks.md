# Implementation Plan: Vercel 500 Error Fix

## Overview

This implementation plan addresses the critical issues causing 500 server errors in the DUB5 chatbot when deployed to Vercel. The approach focuses on fixing import paths, eliminating duplicate endpoints, adapting static file serving for serverless, implementing timeout management, and adding comprehensive error handling.

## Tasks

- [ ] 1. Fix import paths and file naming
  - [x] 1.1 Rename `api/chatbot_backup_old.py` to `api/chatbot_backup.py`
    - Rename the file to match the import statement in `api/index.py`
    - _Requirements: 2.1, 2.2_
  
  - [x] 1.2 Verify all imports use absolute paths from `api` package
    - Update any relative imports to absolute imports
    - Ensure consistency across all files in the `api` package
    - _Requirements: 2.3, 2.4, 6.1_
  
  - [ ]* 1.3 Write unit test for import resolution
    - Test that `api.chatbot_backup` can be imported successfully
    - Test that all required modules are importable
    - _Requirements: 2.1, 2.3, 6.4_

- [ ] 2. Eliminate duplicate endpoint definitions
  - [x] 2.1 Remove duplicate `/health` endpoint from `api/index.py`
    - Keep the comprehensive health check implementation (around line 150)
    - Remove the simple health check (around line 15)
    - _Requirements: 1.1, 1.2_
  
  - [ ]* 2.2 Write property test for unique endpoints
    - **Property 1: No Duplicate Endpoints**
    - **Validates: Requirements 1.1**
    - Test that all registered endpoint paths are unique
    - _Requirements: 1.1_

- [ ] 3. Implement environment detection and configuration
  - [x] 3.1 Create `api/environment.py` module
    - Implement `Environment` class with static methods for detection
    - Add methods: `is_vercel()`, `get_root_path()`, `get_cache_dir()`
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_
  
  - [x] 3.2 Create `ServerlessConfig` dataclass in `api/config.py`
    - Add configuration model with environment-specific settings
    - Implement `from_environment()` class method
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_
  
  - [ ]* 3.3 Write property tests for environment detection
    - **Property 9: Environment Detection**
    - **Property 10: Environment-Specific Temporary Storage**
    - **Property 11: Environment-Specific Root Path**
    - **Validates: Requirements 9.1, 9.2, 9.3, 9.4, 9.5**
    - Test environment detection with mocked environment variables
    - Test path selection based on environment
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

- [ ] 4. Adapt static file serving for serverless
  - [x] 4.1 Update `api/index.py` to conditionally mount static files
    - Only mount `StaticFiles` when not running on Vercel
    - Use environment detection to determine behavior
    - _Requirements: 3.1, 3.3_
  
  - [x] 4.2 Update root path handler to read HTML files directly
    - Modify `get_chatbot_html()` to read from `public/chatbot.html`
    - Add proper error handling for missing files
    - _Requirements: 3.4, 4.4_
  
  - [ ]* 4.3 Write property test for static file mounting
    - **Property 12: Static File Mounting Based on Environment**
    - **Validates: Requirements 3.1, 3.3**
    - Test that StaticFiles.mount is not called in Vercel environment
    - _Requirements: 3.1, 3.3_
  
  - [ ]* 4.4 Write unit tests for file serving
    - Test that root path returns HTML content
    - Test that missing files return 404 with descriptive message
    - _Requirements: 3.4, 4.4_

- [x] 5. Checkpoint - Ensure basic application starts
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 6. Implement timeout management
  - [x] 6.1 Create `api/timeout_manager.py` module
    - Implement `with_timeout_protection()` async generator wrapper
    - Add heartbeat generation every 10 seconds
    - Add timeout enforcement at 50 seconds
    - _Requirements: 5.1, 5.2, 5.3_
  
  - [x] 6.2 Update `stream_chat_completion()` to use timeout wrapper
    - Wrap the AI streaming generator with timeout protection
    - Configure g4f and Pollinations clients with 50-second timeouts
    - _Requirements: 5.1, 5.3, 5.4, 5.5_
  
  - [ ]* 6.3 Write property test for immediate heartbeat
    - **Property 5: Immediate Heartbeat on Stream Start**
    - **Validates: Requirements 5.1**
    - Test that first message in stream is a heartbeat
    - _Requirements: 5.1_
  
  - [ ]* 6.4 Write unit tests for timeout handling
    - Test that streams timeout after 50 seconds
    - Test that timeout configuration is set correctly
    - _Requirements: 5.3, 5.4, 5.5_

- [ ] 7. Implement comprehensive error handling
  - [x] 7.1 Create `api/error_handler.py` module
    - Define custom exception classes (ServerlessError, ImportFailureError, TimeoutError)
    - Implement `handle_import_error()` function
    - Implement `handle_ai_provider_error()` function
    - Implement `log_error()` function with structured logging
    - _Requirements: 4.1, 4.2, 4.4_
  
  - [x] 7.2 Update `api/index.py` to use error handlers
    - Wrap all endpoint handlers in try-except blocks
    - Return structured error responses using error handler
    - _Requirements: 4.1, 4.4_
  
  - [x] 7.3 Update import statements to use fallback logic
    - Wrap g4f import in try-except with mock fallback
    - Add error logging for import failures
    - _Requirements: 4.2, 4.3_
  
  - [ ]* 7.4 Write property tests for error handling
    - **Property 2: Structured Error Responses**
    - **Property 3: Import Fallback Behavior**
    - **Property 4: File Operation Error Handling**
    - **Validates: Requirements 4.1, 4.2, 4.4**
    - Test that all exceptions return structured error responses
    - Test that import failures use fallback implementations
    - Test that file operation errors return appropriate status codes
    - _Requirements: 4.1, 4.2, 4.4_

- [x] 8. Checkpoint - Ensure error handling works
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 9. Implement AI provider fallback system
  - [x] 9.1 Create `api/provider_manager.py` module
    - Implement `ProviderManager` class
    - Add methods: `get_next_provider()`, `record_failure()`, `record_success()`
    - Implement failure tracking and cooldown logic
    - _Requirements: 8.1, 8.3, 8.4_
  
  - [x] 9.2 Update `stream_chat_completion()` to use ProviderManager
    - Replace direct provider calls with ProviderManager
    - Implement automatic fallback on provider failure
    - Add error handling for all providers failing
    - _Requirements: 8.1, 8.2_
  
  - [ ]* 9.3 Write property tests for provider fallback
    - **Property 6: Provider Fallback on Failure**
    - **Property 7: Provider Failure Tracking**
    - **Property 8: Provider Cooldown After Consecutive Failures**
    - **Validates: Requirements 8.1, 8.3, 8.4**
    - Test that g4f failure triggers Pollinations fallback
    - Test that failure counts are tracked correctly
    - Test that 3 consecutive failures trigger cooldown
    - _Requirements: 8.1, 8.3, 8.4_

- [ ] 10. Update health check endpoint
  - [x] 10.1 Enhance health check to test both AI backends
    - Keep existing comprehensive health check implementation
    - Ensure it tests both g4f and Pollinations AI
    - Add timeout protection to health checks (10 seconds max)
    - _Requirements: 10.1, 10.2, 10.4_
  
  - [x] 10.2 Update health check error handling
    - Ensure errors are included in response
    - Ensure HTTP 200 is returned even with unhealthy backends
    - _Requirements: 10.3, 10.5_
  
  - [ ]* 10.3 Write property tests for health check
    - **Property 13: Health Check Error Inclusion**
    - **Property 14: Health Check Always Returns 200**
    - **Validates: Requirements 10.3, 10.5**
    - Test that backend failures include error messages
    - Test that health check always returns 200 status
    - _Requirements: 10.3, 10.5_
  
  - [ ]* 10.4 Write unit tests for health check
    - Test that health check tests both backends
    - Test that response includes status for each backend
    - _Requirements: 10.1, 10.2_

- [ ] 11. Update Vercel configuration
  - [x] 11.1 Verify `vercel.json` configuration
    - Ensure function timeout is set to 60 seconds
    - Ensure memory is set to 1024 MB
    - Ensure Python 3.9 runtime is specified
    - Verify static file routing is configured correctly
    - _Requirements: 3.5, 7.1, 7.2, 7.3_
  
  - [x] 11.2 Update route configuration for static files
    - Ensure static files are served through Vercel routing
    - Ensure API routes are directed to serverless function
    - _Requirements: 3.2, 3.5_

- [ ] 12. Optimize for cold starts
  - [x] 12.1 Implement lazy loading for heavy dependencies
    - Move g4f import to function scope where used
    - Delay AI model initialization until first request
    - _Requirements: 7.5_
  
  - [x] 12.2 Add initialization logging
    - Log startup time and loaded modules
    - Add performance metrics for cold start tracking
    - _Requirements: 7.4_

- [ ] 13. Final integration and testing
  - [x] 13.1 Run all unit tests
    - Verify all unit tests pass
    - _Requirements: All_
  
  - [ ]* 13.2 Run all property tests with 100 iterations
    - Verify all property tests pass with 100 iterations
    - _Requirements: All_
  
  - [x] 13.3 Test locally with environment variable mocking
    - Test with VERCEL=1 to simulate Vercel environment
    - Test without VERCEL to simulate local environment
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_
  
  - [x] 13.4 Verify all endpoints are accessible
    - Test `/health` endpoint
    - Test `/` root endpoint
    - Test `/api/chatbot` endpoint
    - _Requirements: 1.1, 1.2, 3.4_

- [x] 14. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties
- Unit tests validate specific examples and edge cases
- The implementation prioritizes fixing critical 500 errors first, then adding robustness
