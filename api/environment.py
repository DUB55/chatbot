"""
Environment detection module for Vercel serverless deployment.

This module provides utilities to detect the runtime environment and configure
paths appropriately for both Vercel serverless and local development environments.
"""

import os


class Environment:
    """
    Environment detection and configuration helper.
    
    Provides static methods to detect whether the application is running on Vercel
    and returns environment-appropriate configuration values.
    """
    
    @staticmethod
    def is_vercel() -> bool:
        """
        Detect whether the application is running on Vercel.
        
        Checks for the presence of the VERCEL environment variable, which is
        automatically set by Vercel in their serverless environment.
        
        Returns:
            bool: True if running on Vercel, False otherwise
        """
        return os.environ.get("VERCEL") is not None
    
    @staticmethod
    def get_root_path() -> str:
        """
        Get the appropriate root path for the FastAPI application.
        
        Vercel routes API requests to /api/*, so the FastAPI root_path must be
        set to /api when running on Vercel. Local development uses no prefix.
        
        Returns:
            str: "/api" if running on Vercel, empty string if running locally
        """
        return "/api" if Environment.is_vercel() else ""
    
    @staticmethod
    def get_cache_dir() -> str:
        """
        Get the appropriate cache directory for temporary file storage.
        
        Vercel serverless functions have write access only to /tmp directory.
        Local development can use a local cache directory.
        
        Returns:
            str: "/tmp/.g4f_cache" if running on Vercel, ".g4f_cache" if running locally
        """
        return "/tmp/.g4f_cache" if Environment.is_vercel() else ".g4f_cache"
