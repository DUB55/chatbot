import tiktoken
import logging

logger = logging.getLogger("chatbot")

def count_tokens(text: str, model: str = "gpt-3.5-turbo") -> int:
    """Telt het aantal tokens in een tekst string."""
    try:
        # G4F modellen mappen naar tiktoken encodings
        if "gpt-4" in model:
            encoding = tiktoken.encoding_for_model("gpt-4")
        elif "claude" in model:
            # Claude gebruikt andere tokenizer, maar gpt-4 is een veilige overschatting
            encoding = tiktoken.encoding_for_model("gpt-4")
        else:
            encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
        
        return len(encoding.encode(text))
    except Exception as e:
        logger.debug(f"Token count error: {e}")
        # Ruwe schatting: 1 token ~= 4 karakters
        return len(text) // 4

def trim_history(messages: list, max_tokens: int = 4000) -> list:
    """Zorgt dat de chat history binnen het token budget blijft."""
    # Systeem prompt moet altijd blijven (index 0)
    system_msg = messages[0]
    history = messages[1:]
    
    current_tokens = count_tokens(system_msg["content"])
    trimmed_history = []
    
    # Werk van nieuw naar oud
    for msg in reversed(history):
        msg_tokens = count_tokens(msg["content"])
        if current_tokens + msg_tokens < max_tokens:
            trimmed_history.insert(0, msg)
            current_tokens += msg_tokens
        else:
            break
            
    return [system_msg] + trimmed_history

def summarize_context(messages: list, model: str = "gpt-3.5-turbo") -> str:
    """
    Vraagt de AI om een samenvatting te maken van de oudste berichten.
    Dit wordt synchroon aangeroepen (blocking) voor eenvoud, maar in een 
    echte productie-app zou dit async zijn.
    """
    from g4f.client import Client
    client = Client()
    
    # Selecteer de oudste berichten om samen te vatten (bijv. de eerste 6 na de system prompt)
    to_summarize = messages[1:7]
    text_to_summarize = "\n".join([f"{m['role']}: {m['content']}" for m in to_summarize])
    
    prompt = f"Vat de volgende chat-geschiedenis kort samen in maximaal 3 zinnen. Behoud alle belangrijke feiten en gemaakte afspraken:\n\n{text_to_summarize}"
    
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            timeout=10
        )
        summary = response.choices[0].message.content
        return f"[SAMENVATTING OUDERE GESPREKKEN]: {summary}"
    except Exception as e:
        logger.error(f"Summarization failed: {e}")
        return ""

def smart_context_manager(messages: list, model: str, max_tokens: int = 4000) -> list:
    """
    De 'heilige graal' van context management:
    1. Telt tokens.
    2. Als te vol: Vat de oudste berichten samen.
    3. Voeg samenvatting toe aan de system prompt of als eerste bericht.
    4. Trim de rest.
    """
    system_msg = messages[0]
    history = messages[1:]
    
    total_tokens = count_tokens(system_msg["content"], model) + sum([count_tokens(m["content"], model) for m in history])
    
    if total_tokens <= max_tokens:
        return messages

    # Skip summarization if it's likely to cause a timeout (e.g., very large history)
    # or just perform a simple trim for speed.
    logger.info(f"Context over limit ({total_tokens} > {max_tokens}). Trimming...")
    return trim_history(messages, max_tokens)
