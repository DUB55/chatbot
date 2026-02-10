from fastapi import FastAPI
app = FastAPI()

@app.get("/api/status")
@app.get("/status")
def status():
    return {"status": "ok", "message": "Ultra-lightweight status check working"}
