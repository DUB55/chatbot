import json
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI()

@app.post("/api/chatbot")
async def simple_test(request: Request):
    try:
        body = await request.json()
        return JSONResponse(content={"received": body.get("input", "no input")})
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)