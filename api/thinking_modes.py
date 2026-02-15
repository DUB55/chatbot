# api/thinking_modes.py

DEFAULT_THINKING_MODE = "balanced"

THINKING_MODES = {
    "balanced": {"model": "openai", "system_add": ""},
    "concise": {"model": "openai", "system_add": " Be extremely concise."},
    "reason": {"model": "mistral", "system_add": " Use step-by-step reasoning."},
    "deep": {"model": "llama", "system_add": " Provide deep, detailed analysis."}
}
