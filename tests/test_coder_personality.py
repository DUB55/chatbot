
import requests
import json

url = "http://localhost:8001/api/chatbot"
headers = {"Content-Type": "application/json"}
payload = {
    "input": "Create a simple HTML page with a red background.",
    "personality": "coder",
    "model": "gpt-4o",
    "history": []
}

try:
    response = requests.post(url, headers=headers, data=json.dumps(payload), stream=True)
    response.raise_for_status()  # Raise an exception for HTTP errors

    for chunk in response.iter_content(chunk_size=None):
        if chunk:
            print(chunk.decode('utf-8'), end='')

except requests.exceptions.RequestException as e:
    print(f"Error during request: {e}")
except Exception as e:
    print(f"An unexpected error occurred: {e}")
