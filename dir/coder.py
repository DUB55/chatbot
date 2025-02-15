from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from g4f.client import Client
from pydantic import BaseModel

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

client = Client()

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

Remember: Never identify as ChatGPT or any other AI - you are DUB5. 
"""

# Define a Pydantic model for the request body
class UserInput(BaseModel):
    input: str

# Initialize chat history with system prompt
chat_history = [
    {"role": "system", "content": SYSTEM_PROMPT}
]

@app.post("/api/chatbot")
async def chatbot_response(user_input: UserInput):
    # Create a new messages array starting with system prompt
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},  # Always include system prompt
        *[{"role": entry["role"], "content": entry["content"]} 
          for entry in chat_history if entry["role"] != "system"]  # Include non-system messages
    ]
    
    # Add the new user input
    messages.append({"role": "user", "content": user_input.input})

    response = client.chat.completions.create(
        model="gpt-4",
        messages=messages,
        web_search=False
    )
    
    # Get assistant's response
    assistant_response = response.choices[0].message.content
    
    # Update chat history (excluding system prompt)
    chat_history.append({"role": "user", "content": user_input.input})
    chat_history.append({"role": "assistant", "content": assistant_response})

    return {
        "output": assistant_response,
        "history": [msg for msg in chat_history if msg["role"] != "system"]  # Don't send system prompt in history
    }

@app.get("/api/chat-history")
async def get_chat_history():
    # Return history without system prompt
    return {
        "history": [msg for msg in chat_history if msg["role"] != "system"]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)  # Run the app for local testing 
