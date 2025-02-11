from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from g4f.client import Client

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

@app.post("/api/chatbot")
async def chatbot_response(user_input: str):
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": user_input}],
        web_search=False
    )
    return {"output": response.choices[0].message.content}  # Return response in JSON format

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)  # Run the app for local testing 
