"""FastAPI application main module."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import ai, health, metrics, orders
from app.core.config import settings
from app.core.logging import setup_logging

# Setup logging
setup_logging()

# Create FastAPI app
app = FastAPI(
    title="Arbitrage Trading Bot API",
    description="API for AI-assisted cryptocurrency arbitrage trading bot",
    version="1.0.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.api.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router)
app.include_router(metrics.router)
app.include_router(orders.router)
app.include_router(ai.router)


@app.on_event("startup")
async def startup_event() -> None:
    """Startup event handler."""
    # TODO: Initialize exchanges, load model, start price stream, etc.
    pass


@app.on_event("shutdown")
async def shutdown_event() -> None:
    """Shutdown event handler."""
    # TODO: Close exchange connections, stop price stream, etc.
    pass


@app.get("/")
async def root() -> dict:
    """
    Root endpoint.

    Returns:
        API information
    """
    return {
        "name": "Arbitrage Trading Bot API",
        "version": "1.0.0",
        "status": "running",
    }

