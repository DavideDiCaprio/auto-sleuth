import uvicorn
from fastapi import FastAPI
from app.routers import api
from dotenv import load_dotenv
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Load Environment Variables (API Keys, DB URLs)
load_dotenv()

from app.database import engine, Base

# Create Database Tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Car Cost Investigator",
    description="AI-powered agent to calculate real ownership costs of used cars.",
    version="1.0.0"
)

# Register Routes (Controllers)
app.include_router(api.router, prefix="/api/v1")
from app.routers import agent
app.include_router(agent.router, prefix="/api/v1")

# Health Check Endpoint
@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "AutoSleuth"}

# Serve Static Files
app.mount("/static", StaticFiles(directory="frontend"), name="static")

# Serve Frontend at Root
@app.get("/")
async def read_index():
    return FileResponse('frontend/index.html')

if __name__ == "__main__":
    # Runs the server on localhost:8000
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)