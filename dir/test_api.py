import requests
import json

BASE_URL = "http://localhost:8000"

def test_chat(model, thinking_mode, input_text):
    print(f"\nTesting: Model={model}, Mode={thinking_mode}")
    url = f"{BASE_URL}/api/chatbot"
    payload = {
        "input": input_text,
        "model": model,
        "thinking_mode": thinking_mode
    }
    
    try:
        response = requests.post(url, json=payload, stream=True)
        if response.status_code != 200:
            print(f"Error: {response.status_code} - {response.text}")
            return

        print("Response: ", end="", flush=True)
        for line in response.iter_lines():
            if line:
                decoded_line = line.decode('utf-8')
                if decoded_line.startswith('data: '):
                    try:
                        data = json.loads(decoded_line[6:])
                        if 'content' in data:
                            print(data['content'], end="", flush=True)
                        elif 'error' in data:
                            print(f"\nAPI Error: {data['error']}")
                    except json.JSONDecodeError:
                        pass
        print("\n" + "-"*50)
    except Exception as e:
        print(f"Request failed: {e}")

def test_backward_compatibility():
    print("\nTesting Backward Compatibility (Old App Style - Input Only)")
    url = f"{BASE_URL}/api/chatbot"
    payload = {
        "input": "Hallo, wie ben jij?"
    }
    
    try:
        response = requests.post(url, json=payload, stream=True)
        if response.status_code == 200:
            print("SUCCESS: Old apps will still work! Default model/mode applied.")
        else:
            print(f"FAILED: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Request failed: {e}")

if __name__ == "__main__":
    # Test matrix
    tests = [
        ("gpt-4o", "fast", "Hello!"),
        ("gpt-4o", "reason", "Explain quantum physics."),
        ("claude-3-opus", "deep", "Analyze the impact of AI on society."),
        ("invalid-model", "fast", "This should fallback."),
    ]
    
    print("Ensure the server is running at http://localhost:8000 before running tests.")
    # test_backward_compatibility()
    # for model, mode, text in tests:
    #     test_chat(model, mode, text)
