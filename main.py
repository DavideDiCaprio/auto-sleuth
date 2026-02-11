import uvicorn
from fastapi import FastAPI
from dotenv import load_dotenv
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.database import engine, Base
from app.routers import fuel, cars, agent

# Load Environment Variables (API Keys, DB URLs)
load_dotenv()

# Create Database Tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Car Cost Investigator",
    description="AI-powered agent to calculate real ownership costs of used cars.",
    version="1.0.0"
)

app.include_router(fuel.router, prefix="/api/v1", tags=["Fuel Price"])
app.include_router(cars.router, prefix="/api/v1", tags=["Cars"])
app.include_router(agent.router, prefix="/api/v1/agent", tags=["Agent"])

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "AutoSleuth"}

# Serve Frontend at Root
@app.get("/")
async def read_index():
    return FileResponse('frontend/index.html')

# Serve Static Files (mounted last to avoid shadowing routes)
app.mount("/static", StaticFiles(directory="frontend"), name="static")

if __name__ == "__main__":
    # Runs the server on localhost:8000
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)