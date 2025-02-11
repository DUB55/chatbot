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

# Define a Pydantic model for the request body
class UserInput(BaseModel):
    input: str

# List to store chat history
chat_history = []

@app.post("/api/chatbot")
async def chatbot_response(user_input: UserInput):
    # Append the user input to chat history
    chat_history.append({"role": "user", "content": user_input.input})

    # Prepare messages for the assistant, including the entire chat history
    messages = [{"role": entry["role"], "content": entry["content"]} for entry in chat_history]

    response = client.chat.completions.create(
        model="gpt-4",
        messages=messages,  # Include the entire chat history
        web_search=False
    )
    
    # Append the assistant's response to chat history
    assistant_response = response.choices[0].message.content
    chat_history.append({"role": "assistant", "content": assistant_response})

    return {
        "output": assistant_response,
        "history": chat_history  # Return the chat history
    }

@app.get("/api/chat-history")
async def get_chat_history():
    return {"history": chat_history}  # Endpoint to retrieve chat history

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)  # Run the app for local testing 
