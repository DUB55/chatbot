import requests
import json
import time
import sys
import pytest

# Mark this as a manual test that should be skipped by default
pytestmark = pytest.mark.skip(reason="Manual integration test - requires running server")

def test_personality(name, input_text, url="http://localhost:8000/api/chatbot"):
    payload = {
        "input": input_text,
        "model": "gpt-4o-mini",
        "thinking_mode": "concise",
        "personality": name
    }
    
    print(f"\n--- Testing Personality: {name} ---")
    start_time = time.time()
    try:
        response = requests.post(url, json=payload, stream=True, timeout=30)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code != 200:
            print(f"Error: {response.text}")
            return False

        has_content = False
        for line in response.iter_lines():
            if line:
                decoded_line = line.decode('utf-8')
                if decoded_line.startswith("data: "):
                    data_str = decoded_line[6:]
                    try:
                        data = json.loads(data_str)
                        if "content" in data:
                            print(f"Content: {data['content']}")
                            has_content = True
                            break # Just one chunk is enough for verification
                        elif "error" in data:
                            print(f"Backend Error: {data['error']}")
                            return False
                    except:
                        continue
        
        duration = time.time() - start_time
        if has_content:
            print(f"SUCCESS: {name} responded in {duration:.2f}s")
            return True
        else:
            print(f"FAILED: No content received for {name}")
            return False
    except Exception as e:
        print(f"Request Exception: {e}")
        return False

if __name__ == "__main__":
    target_url = "http://localhost:8000/api/chatbot"
    if len(sys.argv) > 1:
        target_url = sys.argv[1]
        print(f"Testing against remote URL: {target_url}")

    tests = [
        ("general", "Hello!"),
        ("teacher", "Explain 1+1"),
        ("writer", "Write a haiku about code"),
        ("coder", "Maak een simpele HTML pagina met een knop die 'Hallo' zegt.")
    ]
    
    results = []
    for p, text in tests:
        results.append(test_personality(p, text, url=target_url))
    
    if all(results):
        print("\nALL PERSONALITIES WORKING!")
    else:
        print("\nSOME PERSONALITIES FAILED.")
