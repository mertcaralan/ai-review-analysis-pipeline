from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.config import get_settings
from api.routers import health, meta, datasets, runs, results, summary

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

# Register routers
app.include_router(health.router)
app.include_router(meta.router)
app.include_router(datasets.router)
app.include_router(runs.router)
app.include_router(results.router)
app.include_router(summary.router)


@app.get("/")
def root():
    """Root endpoint with API information."""
    return {
        "message": "Review Analyzer API",
        "version": settings.VERSION,
        "docs": "/docs",
        "redoc": "/redoc",
        "health": "/health",
        "endpoints": {
            "datasets": "/datasets",
            "runs": "/runs",
            "summary": "/runs/{run_id}/summary",
            "meta": "/meta/schema",
        },
    }
