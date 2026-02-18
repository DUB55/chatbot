import requests
import json

# Test all personalities
personalities = ["general", "coder"]
test_message = "Hello, how are you?"

for personality in personalities:
    print(f"\n=== Testing {personality} personality ===")
    
    url = "http://localhost:8001/api/chatbot"
    headers = {"Content-Type": "application/json"}
    payload = {
        "input": test_message,
        "personality": personality,
        "model": "gpt-4o",
        "history": []
    }
    
    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload), stream=True, timeout=30)
        response.raise_for_status()
        
        chunks_received = 0
        for chunk in response.iter_content(chunk_size=1024):
            if chunk:
                decoded = chunk.decode('utf-8')
                print(f"Chunk {chunks_received}: {decoded[:100]}...")
                chunks_received += 1
                if chunks_received > 5:  # Limit output
                    break
        
        print(f"✅ {personality}: SUCCESS - {chunks_received} chunks received")
        
    except Exception as e:
        print(f"❌ {personality}: FAILED - {e}")

print("\n=== Test Complete ===")
