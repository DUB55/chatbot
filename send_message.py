import httpx
import asyncio
import json

async def send_coder_message():
    url = "http://localhost:8000/api/chatbot"
    headers = {"Content-Type": "application/json"}
    payload = {
        "input": "Create a simple HTML page with a blue background and a 'Hello DUB5' heading.",
        "history": [],
        "personality": "coder"
    }

    print(f"Sending message to {url} with personality: coder")
    try:
        async with httpx.AsyncClient() as client:
            async with client.stream("POST", url, headers=headers, json=payload, timeout=60.0) as response:
                response.raise_for_status()
                print(f"Received HTTP Status: {response.status_code}")
                async for chunk in response.aiter_bytes():
                    try:
                        decoded_chunk = chunk.decode('utf-8')
                        # SSE events start with 'data: '
                        if decoded_chunk.startswith("data: "):
                            json_data = decoded_chunk[len("data: "):].strip()
                            if json_data == "[DONE]":
                                print("Stream finished.")
                                break
                            try:
                                event_data = json.loads(json_data)
                                if "content" in event_data:
                                    print(event_data["content"], end='')
                                elif "error" in event_data:
                                    print(f"\nError from chatbot: {event_data['error']}")
                                elif "type" in event_data and event_data["type"] == "metadata":
                                    print(f"\nMetadata: {event_data}")
                            except json.JSONDecodeError:
                                print(f"\nFailed to decode JSON from chunk: {json_data}")
                        else:
                            print(f"\nRaw chunk: {decoded_chunk}")
                    except UnicodeDecodeError:
                        print(f"\nUnicodeDecodeError: Could not decode chunk: {chunk}")
    except httpx.HTTPStatusError as e:
        print(f"\nHTTP error occurred: {e.response.status_code} - {e.response.text}")
    except httpx.RequestError as e:
        print(f"\nRequest error occurred: {e}")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")

if __name__ == "__main__":
    asyncio.run(send_coder_message())
