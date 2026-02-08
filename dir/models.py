AVAILABLE_MODELS = {
    # --- Top Tier (Coding & Logic) ---
    "gpt-4o": "gpt-4o",
    "gpt-4o-mini": "gpt-4o-mini",
    "gpt-4-turbo": "gpt-4-turbo",
    "claude-3.5-sonnet": "claude-3.5-sonnet",
    "claude-3-opus": "claude-3-opus",
    "gemini-1.5-pro": "gemini-1.5-pro",
    "gemini-1.5-flash": "gemini-1.5-flash",
    
    # --- Open Source Giants ---
    "llama-3.1-405b": "llama-3.1-405b",
    "llama-3.1-70b": "llama-3.1-70b",
    "llama-3.1-8b": "llama-3.1-8b",
    "mixtral-8x22b": "mixtral-8x22b",
    "qwen-2.5-72b": "qwen-2.5-72b",
    
    # --- Fast & Reliable Fallbacks ---
    "gpt-3.5-turbo": "gpt-3.5-turbo",
    "mixtral-8x7b": "mixtral-8x7b",
    "blackbox": "blackbox",
    "command-r": "command-r"
}

DEFAULT_MODEL = "gpt-4o"
FALLBACK_MODEL = "gpt-3.5-turbo"

# List of providers that are known to be free and stable (No API key required)
# Updated for g4f 7.0.0
STABLE_PROVIDERS = [
    "PollinationsAI",
    "DeepInfra",
    "ApiAirforce",
    "HuggingFace",
    "BlackboxPro",
    "ItalyGPT",
    "LMArena",
    "OperaAria",
    "GlhfChat",
    "PuterJS",
    "TeachAnything",
    "DarkAI",
    "DuckDuckGo"
]

# Providers that support web search natively
SEARCH_PROVIDERS = [
    "Blackbox",
    "DuckDuckGo",
    "You",
    "Bing",
    "OperaAria"
]
