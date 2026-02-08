import requests
import json

BASE_URL = "http://localhost:8000"

def verify_model(model_name):
    print(f"\n--- Verifying Model: {model_name} ---")
    url = f"{BASE_URL}/api/chatbot"
    
    # Question designed to reveal identity or knowledge cutoff
    payload = {
        "input": "Exactly which model are you? What is your knowledge cutoff date? Who developed you?",
        "model": model_name,
        "thinking_mode": "reason"
    }
    
    try:
        response = requests.post(url, json=payload, stream=True)
        if response.status_code == 200:
            full_response = ""
            for line in response.iter_lines():
                if line:
                    decoded_line = line.decode('utf-8')
                    if decoded_line.startswith('data: '):
                        content = decoded_line[6:]
                        if content != "[DONE]":
                            full_response += content
            print(f"Response: {full_response}")
            
            # Basic checks
            if "gpt-4" in full_response.lower() or "openai" in full_response.lower():
                print("Result: Likely an OpenAI model.")
            elif "claude" in full_response.lower() or "anthropic" in full_response.lower():
                print("Result: Likely an Anthropic model.")
            elif "llama" in full_response.lower() or "meta" in full_response.lower():
                print("Result: Likely a Meta model.")
            else:
                print("Result: Identity unclear or generic response.")
        else:
            print(f"FAILED: {response.status_code}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    models_to_test = ["gpt-4o", "claude-3-opus", "llama-3-70b"]
    for m in models_to_test:
        verify_model(m)
