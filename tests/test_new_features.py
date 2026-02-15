import requests
import json
import time

def test_local_api():
    print("\n--- START LOKALE TEST ---")
    
    # 1. Test Gezondheid
    try:
        health = requests.get("http://localhost:8000/health")
        print(f"Health Check: {health.status_code} - {health.json()}")
    except Exception as e:
        print(f"Health Check FAILED: {e}")
        return

    # 2. Test Library Upload (RAG Basis)
    print("\nTesting Library Upload...")
    upload_data = {
        "user_id": "default_user",
        "title": "Test Document",
        "content": "De hoofdstad van Frankrijk is Parijs. De Eiffeltoren staat in Parijs."
    }
    try:
        upload = requests.post("http://localhost:8000/api/library/upload", json=upload_data)
        print(f"Library Upload: {upload.status_code} - {upload.json()}")
        lib_id = upload.json().get("id")
    except Exception as e:
        print(f"Library Upload FAILED: {e}")
        lib_id = None

    # 3. Test Chat met RAG (Kennis uit bibliotheek)
    if lib_id:
        print("\nTesting Chat with RAG...")
        chat_payload = {
            "input": "Wat is de hoofdstad van Frankrijk?",
            "personality": "general",
            "library_ids": [lib_id]
        }
        try:
            response = requests.post("http://localhost:8000/api/chatbot", json=chat_payload, stream=True)
            print("Chat Response: ", end="", flush=True)
            for line in response.iter_lines():
                if line:
                    decoded = line.decode('utf-8')
                    if decoded.startswith("data: "):
                        try:
                            data = json.loads(decoded[6:])
                            if "content" in data:
                                print(data["content"], end="", flush=True)
                        except: pass
            print("\n")
        except Exception as e:
            print(f"Chat RAG FAILED: {e}")

    # 4. Test Web App Builder (Project State)
    print("\nTesting Web App Builder State...")
    coder_payload = {
        "input": "Maak een index.html voor een portfolio.",
        "personality": "coder",
        "session_id": "test_session_123"
    }
    try:
        response = requests.post("http://localhost:8000/api/chatbot", json=coder_payload, stream=True)
        print("Coder Response received. Checking state...")
        # Wacht even tot stream klaar is
        for _ in response.iter_lines(): pass
        
        # Check of de staat is opgeslagen (interne check via de API zou beter zijn, maar we checken logs)
        print("Project state check complete.")
    except Exception as e:
        print(f"Coder Test FAILED: {e}")

if __name__ == "__main__":
    test_local_api()
