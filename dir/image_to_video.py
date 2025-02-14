from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from PIL import Image, ImageDraw, ImageFont
import io
import base64
from typing import List
import numpy as np

app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def create_frame(image: Image.Image, text: str, frame_number: int, total_frames: int) -> Image.Image:
    # Create a copy of the image for this frame
    frame = image.copy()
    draw = ImageDraw.Draw(frame)
    
    # Calculate text position (centered at bottom)
    width, height = frame.size
    try:
        # Try to use a default system font
        font = ImageFont.truetype("arial.ttf", 40)
    except:
        # Fallback to default font
        font = ImageFont.load_default()
    
    # Get text size
    text_bbox = draw.textbbox((0, 0), text, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_x = (width - text_width) // 2
    text_y = height - 60  # 60 pixels from bottom
    
    # Add text with outline for better visibility
    outline_color = "black"
    text_color = "white"
    outline_width = 2
    
    # Draw text outline
    for adj in range(-outline_width, outline_width + 1):
        for adj2 in range(-outline_width, outline_width + 1):
            if adj != 0 or adj2 != 0:
                draw.text((text_x + adj, text_y + adj2), text, font=font, fill=outline_color)
    
    # Draw main text
    draw.text((text_x, text_y), text, font=font, fill=text_color)
    
    return frame

@app.post("/api/image-to-video")
async def create_video(
    image: UploadFile = File(...),
    text: str = Form(...),
    duration: int = Form(5)
):
    try:
        # Read and validate the image
        contents = await image.read()
        img = Image.open(io.BytesIO(contents))
        
        # Convert to RGB if necessary
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Create frames
        fps = 30
        total_frames = duration * fps
        frames: List[Image.Image] = []
        
        # Generate frames
        for i in range(total_frames):
            frame = create_frame(img, text, i, total_frames)
            frames.append(frame)
        
        # Save frames as animated GIF instead of MP4
        # This is more reliable in serverless environment
        output_buffer = io.BytesIO()
        frames[0].save(
            output_buffer,
            format='GIF',
            save_all=True,
            append_images=frames[1:],
            duration=1000/fps,  # Duration for each frame in milliseconds
            loop=0
        )
        
        # Convert to base64
        output_buffer.seek(0)
        gif_data = output_buffer.getvalue()
        gif_base64 = base64.b64encode(gif_data).decode()
        
        return JSONResponse({
            "message": "Animation created successfully",
            "video_data": f"data:image/gif;base64,{gif_base64}"
        })
        
    except Exception as e:
        print(f"Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Root endpoint for health check
@app.get("/")
async def root():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 
