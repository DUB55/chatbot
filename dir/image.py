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

@app.post("/api/image")
async def generate_image(user_input: UserInput):
    try:
        response = client.images.generate(
            model="flux",
            prompt=user_input.input,
            response_format="url"
        )
        image_url = response.data[0].url  # Get the image URL
        return {"url": image_url}  # Return the image URL in JSON format
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)  # Run the app for local testing
