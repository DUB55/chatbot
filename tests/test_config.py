"""
Unit tests for the ServerlessConfig dataclass.
"""

import pytest
from api.config import ServerlessConfig


class TestServerlessConfig:
    """Test suite for ServerlessConfig class."""
    
    def test_from_environment_on_vercel(self, monkeypatch):
        """Test that from_environment() creates correct config when running on Vercel."""
        monkeypatch.setenv("VERCEL", "1")
        config = ServerlessConfig.from_environment()
        
        assert config.is_vercel is True
        assert config.root_path == "/api"
        assert config.cache_dir == "/tmp/.g4f_cache"
        assert config.max_duration == 60
        assert config.memory_mb == 1024
        assert config.python_version == "3.9"
    
    def test_from_environment_locally(self, monkeypatch):
        """Test that from_environment() creates correct config when running locally."""
        monkeypatch.delenv("VERCEL", raising=False)
        config = ServerlessConfig.from_environment()
        
        assert config.is_vercel is False
        assert config.root_path == ""
        assert config.cache_dir == ".g4f_cache"
        assert config.max_duration == 60
        assert config.memory_mb == 1024
        assert config.python_version == "3.9"
    
    def test_serverless_config_defaults(self):
        """Test that ServerlessConfig has correct default values."""
        config = ServerlessConfig(
            is_vercel=True,
            root_path="/api",
            cache_dir="/tmp/.g4f_cache"
        )
        
        assert config.max_duration == 60
        assert config.memory_mb == 1024
        assert config.python_version == "3.9"
    
    def test_serverless_config_custom_values(self):
        """Test that ServerlessConfig accepts custom values."""
        config = ServerlessConfig(
            is_vercel=True,
            root_path="/custom",
            cache_dir="/custom/cache",
            max_duration=120,
            memory_mb=2048,
            python_version="3.10"
        )
        
        assert config.is_vercel is True
        assert config.root_path == "/custom"
        assert config.cache_dir == "/custom/cache"
        assert config.max_duration == 120
        assert config.memory_mb == 2048
        assert config.python_version == "3.10"
