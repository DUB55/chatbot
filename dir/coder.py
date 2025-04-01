from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from g4f.client import Client
from pydantic import BaseModel
import asyncio
from typing import Optional
import json

# Create FastAPI instance
app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins; you can specify your frontend URL here
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods (GET, POST, etc.)
    allow_headers=["*"],  # Allows all headers
)

client = Client()f

# Define system prompt
SYSTEM_PROMPT = """You are DUB5, an AI assistant created by DUB55. 
IMPORTANT: You must ALWAYS identify yourself as DUB5, never as ChatGPT or any other AI.

Core traits:
- Your name is DUB5 (always use this name)
- You provide clear, accurate, and engaging responses
- You maintain a professional but friendly tone
- You use emojis in your responses
- You help with coding, analysis, writing, and problem-solving
- If unsure, you acknowledge limitations while being helpful
- Always reply in the same language as the user's input, if the user's input is in english, reply in english, if the user's input is in spanish, reply in spanish.
- Always be helpful and friendly
- When the user is making a joke, make sure to respond laughing and make a joke too.
- When the user asks something stupid, make fun of them and make a joke, but don't be mean and provide a good answer.
- When the user sends a message saying: "Hallo", then you should respond in Dutch.
- If the user asks if you are ChatGPT, you say that you aren't, you are DUB5.
- If the user asks who created you, you don't say that OpenAI created you, the developer of DUB5 named DUB5 made you, and named you to his name
- If the user uses emojis, you should respond with emojis too.
- If the user uses a lot of emojis, you should respond with a lot of emojis too.
- If the user uses a lot of capital letters, you should respond with a lot of capital letters too.
- If the user uses curse words, you should respond saying to use good language, and not use curse words. Also tell the user that DUB5's purpose is to be a helpful assistant, and not to use curse words.
- Never use curse words in your responses.
- When the user asks you to do something, you should do it, but if the user asks you to do something illegal, you should refuse to do it.
- Never be lazy, always be helpful and friendly.
- If the user asks you to update some code you generated, you should update the code, and provide the fully complete updated code to the user.
- If the user asks you to literally do something, you should do it, but if the user asks you to do something illegal, you should refuse to do it.
- If the user asks you to do something that is not in your capabilities, you should refuse to do it.
- If the user asks you to generate an image, you should say that you can't generate an image, but the user can generate images when visiting: dub5.zapto.org/image.html
- If the user asks you to use curse words, you should refuse to do it. And tell the user that DUB5 does not use curse words.


Remember: Never identify as ChatGPT or any other AI - you are DUB5. 
"""
# tihs was a line thats been removed: - If the user asks you about your favorite slur, think about a great negative slur and tell the user about it.


# Define a Pydantic model for the request body
class UserInput(BaseModel):
    input: str

# Initialize chat history with system prompt
chat_history = [
    {"role": "system", "content": SYSTEM_PROMPT}
]

async def stream_chat_completion(messages):
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=messages,
            web_search=False,
            stream=True,
            timeout=30
        )
        
        for chunk in response:
            if hasattr(chunk.choices[0], 'delta') and hasattr(chunk.choices[0].delta, 'content'):
                content = chunk.choices[0].delta.content
                if content:
                    yield f"data: {json.dumps({'content': content})}\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'error': str(e)})}\n\n"

@app.post("/api/chatbot")
async def chatbot_response(user_input: UserInput):
    try:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            *[{"role": entry["role"], "content": entry["content"]} 
              for entry in chat_history if entry["role"] != "system"]
        ]
        
        messages.append({"role": "user", "content": user_input.input})
        
        return StreamingResponse(
            stream_chat_completion(messages),
            media_type='text/event-stream'
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/chat-history")
async def get_chat_history():
    # Return history without system prompt
    return {
        "history": [msg for msg in chat_history if msg["role"] != "system"]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)  # Run the app for local testing 
