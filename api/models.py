# api/models.py

DEFAULT_MODEL = "openai"
FALLBACK_MODEL = "openai" # Default fallback if primary fails

MODELS = {
    "gpt-4o": "openai",
    "gpt-4o-mini": "openai",
    "mistral": "mistral",
    "llama": "llama",
    "search": "search",
    "claude-3-haiku": "openai", # Fallback to openai for haiku
    "deepseek": "deepseek",
    "flux": "flux" # Image model
}

# A list of all available models for reference
AVAILABLE_MODELS = list(MODELS.keys())

# Providers considered stable for general use
STABLE_PROVIDERS = [
    "openai",
    "mistral",
    "llama",
    "deepseek"
]

# Providers that can perform web searches
SEARCH_PROVIDERS = [
    "search" # This is a placeholder for a dedicated search model/provider
]
