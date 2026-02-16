"""
Unit tests for the Environment detection module.
"""

import os
import pytest
from api.environment import Environment


class TestEnvironment:
    """Test suite for Environment class."""
    
    def test_is_vercel_when_env_var_set(self, monkeypatch):
        """Test that is_vercel() returns True when VERCEL env var is set."""
        monkeypatch.setenv("VERCEL", "1")
        assert Environment.is_vercel() is True
    
    def test_is_vercel_when_env_var_not_set(self, monkeypatch):
        """Test that is_vercel() returns False when VERCEL env var is not set."""
        monkeypatch.delenv("VERCEL", raising=False)
        assert Environment.is_vercel() is False
    
    def test_get_root_path_on_vercel(self, monkeypatch):
        """Test that get_root_path() returns /api when running on Vercel."""
        monkeypatch.setenv("VERCEL", "1")
        assert Environment.get_root_path() == "/api"
    
    def test_get_root_path_locally(self, monkeypatch):
        """Test that get_root_path() returns empty string when running locally."""
        monkeypatch.delenv("VERCEL", raising=False)
        assert Environment.get_root_path() == ""
    
    def test_get_cache_dir_on_vercel(self, monkeypatch):
        """Test that get_cache_dir() returns /tmp/.g4f_cache on Vercel."""
        monkeypatch.setenv("VERCEL", "1")
        assert Environment.get_cache_dir() == "/tmp/.g4f_cache"
    
    def test_get_cache_dir_locally(self, monkeypatch):
        """Test that get_cache_dir() returns .g4f_cache locally."""
        monkeypatch.delenv("VERCEL", raising=False)
        assert Environment.get_cache_dir() == ".g4f_cache"
