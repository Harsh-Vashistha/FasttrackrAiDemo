"""
FasttrackrAI — Financial Advisor Client Management System
FastAPI entry point.
"""

from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

from database import Base, engine
from routers import households, insights, upload, review


# ---------------------------------------------------------------------------
# Lifespan: create DB tables on startup
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    Base.metadata.create_all(bind=engine)
    yield
    # Shutdown (nothing to do)


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

app = FastAPI(
    title="FasttrackrAI — Financial Advisor API",
    description="Backend API for managing household financial data.",
    version="1.0.0",
    lifespan=lifespan,
)

# ---- CORS -----------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- Routers --------------------------------------------------------------
app.include_router(households.router, prefix="/api")
app.include_router(upload.router, prefix="/api")
app.include_router(insights.router, prefix="/api")
app.include_router(review.router, prefix="/api")


# ---------------------------------------------------------------------------
# Root
# ---------------------------------------------------------------------------

@app.get("/", tags=["health"])
def root():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Dev entrypoint: python main.py  (or uvicorn main:app --reload --port 8000)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
