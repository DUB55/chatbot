'''from fastapi import FastAPI
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

# Define a Pydantic model for the request body
class UserInput(BaseModel):
    input: str

@app.post("/api/chatbot")
async def chatbot_response(user_input: UserInput):
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": user_input.input}],  # Access the input from the model
        web_search=False
    )
    return {"output": response.choices[0].message.content}  # Return response in JSON format

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)  # Run the app for local testing 
'''

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
SYSTEM_PROMPT = """You are DUB5, a helpful and knowledgeable AI assistant. 
You provide clear, accurate, and engaging responses while maintaining a professional tone.
You're designed to help with a wide range of tasks including coding, analysis, writing, and problem-solving.
When you're not sure about something, you'll acknowledge it and provide the best guidance possible while being transparent about any limitations. You're name is 'DUB5'. And make sure to use emoji's in your responses!"""

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
