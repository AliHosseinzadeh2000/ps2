"""FastAPI application main module."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import ai, health, metrics, orders, risk, history
from app.api.services import (
    close_exchanges,
    get_arbitrage_engine,
    get_exchanges,
    get_order_executor,
    get_price_stream,
)
from app.core.config import settings
from app.core.logging import setup_logging
from app.db.db import init_db

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
app.include_router(risk.router)
app.include_router(history.router)


@app.on_event("startup")
async def startup_event() -> None:
    """Startup event handler."""
    # Initialize database
    await init_db()

    # Initialize exchanges, arbitrage engine, and order executor
    get_exchanges()
    arbitrage_engine = get_arbitrage_engine()
    get_order_executor()
    
    # Initialize and start price stream with default symbols
    price_stream = get_price_stream()
    # Subscribe arbitrage engine to price updates
    price_stream.subscribe(arbitrage_engine.on_price_update)
    
    # Start price stream for default symbols (can be configured)
    default_symbols = getattr(settings.trading, "default_symbols", ["BTCUSDT", "ETHUSDT"])
    await price_stream.start(default_symbols)


@app.on_event("shutdown")
async def shutdown_event() -> None:
    """Shutdown event handler."""
    # Stop price stream
    from app.api.services import get_price_stream
    price_stream = get_price_stream()
    if price_stream.is_running():
        await price_stream.stop()
    
    # Close exchange connections
    await close_exchanges()


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
