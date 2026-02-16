"""
Unit tests for root path handler in api/index.py.
Tests that the root path handler reads HTML files directly with proper error handling.
"""

import os
import pytest
from unittest.mock import patch, mock_open, MagicMock
from fastapi.testclient import TestClient


class TestRootPathHandler:
    """Test suite for root path handler."""
    
    def test_root_path_returns_html_content(self, monkeypatch):
        """
        Test that root path returns HTML content from public/chatbot.html.
        Validates: Requirements 3.4
        """
        # Ensure we're in local environment for this test
        monkeypatch.delenv("VERCEL", raising=False)
        
        # Import after setting environment
        import importlib
        import api.index
        importlib.reload(api.index)
        
        client = TestClient(api.index.app)
        
        # Make request to root path
        response = client.get("/")
        
        # Verify response
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/html; charset=utf-8"
        # The response should contain HTML content
        assert "<!DOCTYPE html>" in response.text or "<html" in response.text
    
    def test_root_path_handles_missing_file(self, monkeypatch):
        """
        Test that root path returns 404 when chatbot.html is missing.
        Validates: Requirements 4.4
        """
        # Ensure we're in local environment
        monkeypatch.delenv("VERCEL", raising=False)
        
        # Mock open to raise FileNotFoundError
        with patch("builtins.open", side_effect=FileNotFoundError("File not found")):
            # Import after setting up mock
            import importlib
            import api.index
            importlib.reload(api.index)
            
            client = TestClient(api.index.app)
            
            # Make request to root path
            response = client.get("/")
            
            # Verify 404 response with structured error
            assert response.status_code == 404
            assert response.headers["content-type"] == "application/json"
            data = response.json()
            assert data["type"] == "error"
            assert data["error_code"] == "FILE_NOT_FOUND"
            assert "Chatbot interface not found" in data["message"]
    
    def test_root_path_handles_permission_error(self, monkeypatch):
        """
        Test that root path returns 500 when permission is denied.
        Validates: Requirements 4.4
        """
        # Ensure we're in local environment
        monkeypatch.delenv("VERCEL", raising=False)
        
        # Mock open to raise PermissionError
        with patch("builtins.open", side_effect=PermissionError("Permission denied")):
            # Import after setting up mock
            import importlib
            import api.index
            importlib.reload(api.index)
            
            client = TestClient(api.index.app)
            
            # Make request to root path
            response = client.get("/")
            
            # Verify 500 response with structured error
            assert response.status_code == 500
            assert response.headers["content-type"] == "application/json"
            data = response.json()
            assert data["type"] == "error"
            assert data["error_code"] == "PERMISSION_DENIED"
            assert "permission" in data["message"].lower() or "permission" in data["details"].lower()
    
    def test_root_path_handles_encoding_error(self, monkeypatch):
        """
        Test that root path returns 500 when encoding error occurs.
        Validates: Requirements 4.4
        """
        # Ensure we're in local environment
        monkeypatch.delenv("VERCEL", raising=False)
        
        # Mock open to raise UnicodeDecodeError when read() is called
        mock_file = MagicMock()
        mock_file.__enter__ = MagicMock(return_value=mock_file)
        mock_file.__exit__ = MagicMock(return_value=False)
        mock_file.read.side_effect = UnicodeDecodeError("utf-8", b"", 0, 1, "invalid")
        
        with patch("builtins.open", return_value=mock_file):
            # Import after setting up mock
            import importlib
            import api.index
            importlib.reload(api.index)
            
            client = TestClient(api.index.app)
            
            # Make request to root path
            response = client.get("/")
            
            # Verify 500 response with structured error
            assert response.status_code == 500
            assert response.headers["content-type"] == "application/json"
            data = response.json()
            assert data["type"] == "error"
            assert data["error_code"] == "ENCODING_ERROR"
            assert "encoding" in data["message"].lower() or "encoding" in data["details"].lower()
    
    def test_root_path_handles_generic_exception(self, monkeypatch):
        """
        Test that root path returns 500 for unexpected errors.
        Validates: Requirements 4.4
        """
        # Ensure we're in local environment
        monkeypatch.delenv("VERCEL", raising=False)
        
        # Mock open to raise generic exception
        with patch("builtins.open", side_effect=Exception("Unexpected error")):
            # Import after setting up mock
            import importlib
            import api.index
            importlib.reload(api.index)
            
            client = TestClient(api.index.app)
            
            # Make request to root path
            response = client.get("/")
            
            # Verify 500 response with structured error
            assert response.status_code == 500
            assert response.headers["content-type"] == "application/json"
            data = response.json()
            assert data["type"] == "error"
            assert data["error_code"] == "INTERNAL_ERROR"
            assert "error" in data["message"].lower() or "unexpected" in data["details"].lower()
