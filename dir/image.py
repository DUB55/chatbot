from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from g4f.client import Client
from pydantic import BaseModel
import asyncio
from concurrent.futures import ThreadPoolExecutor

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
executor = ThreadPoolExecutor()  # Create a thread pool executor

# Define a Pydantic model for the request body
class UserInput(BaseModel):
    input: str

def generate_image_sync(prompt):
    """Synchronous function to generate an image."""
    response = client.images.generate(
        model="flux",
        prompt=prompt,
        response_format="url"
    )
    return response.data[0].url  # Return the image URL

@app.post("/api/image")
async def generate_image(user_input: UserInput):
    """Asynchronous endpoint to generate an image."""
    try:
        # Use run_in_executor to call the synchronous function
        loop = asyncio.get_event_loop()
        image_url = await loop.run_in_executor(executor, generate_image_sync, user_input.input)
        return {"url": image_url}  # Return the image URL in JSON format
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)  # Run the app for local testing
