"""Health check endpoints."""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/health", tags=["health"])


class HealthResponse(BaseModel):
    """Health check response model."""

    status: str
    timestamp: float


@router.get("", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Health check endpoint.

    Returns:
        Health status
    """
    import time

    return HealthResponse(status="healthy", timestamp=time.time())


@router.get("/ready")
async def readiness_check() -> dict:
    """
    Readiness check endpoint.

    Returns:
        Readiness status
    """
    # TODO: Add actual readiness checks (database, exchanges, etc.)
    return {"status": "ready"}


@router.get("/live")
async def liveness_check() -> dict:
    """
    Liveness check endpoint.

    Returns:
        Liveness status
    """
    return {"status": "alive"}

