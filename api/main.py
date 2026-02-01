from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    description="AI-powered app review analysis API",
)

# CORS middleware for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    """Root endpoint."""
    return {
        "message": "Review Analyzer API",
        "version": settings.VERSION,
        "docs": "/docs",
        "health": "/health",
    }
