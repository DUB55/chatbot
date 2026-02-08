from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncio
from concurrent.futures import ThreadPoolExecutor

# Mock g4f if it fails to import (for Vercel deployment stability)
try:
    import g4f
    from g4f.client import Client
    
    # Disable noise
    if hasattr(g4f, 'debug'):
        g4f.debug.version_check = False
        g4f.debug.logging = False
except Exception as ge:
    class MockClient:
        def __init__(self, *args, **kwargs): pass
        class Images:
            def generate(self, *args, **kwargs):
                raise Exception("G4F niet beschikbaar in deze omgeving")
        images = Images()
    Client = MockClient

# Create FastAPI instance
app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

try:
    client = Client()
except:
    client = None
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
