"""Trading metrics endpoints."""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Dict, List, Optional

router = APIRouter(prefix="/metrics", tags=["metrics"])


class TradingMetrics(BaseModel):
    """Trading metrics response model."""

    total_trades: int = 0
    profitable_trades: int = 0
    total_profit: float = 0.0
    total_volume: float = 0.0
    win_rate: float = 0.0
    active_opportunities: int = 0


class OpportunityMetrics(BaseModel):
    """Opportunity metrics."""

    symbol: str
    buy_exchange: str
    sell_exchange: str
    spread_percent: float
    net_profit: float
    max_quantity: float


# In-memory metrics storage (replace with database in production)
_metrics_store: Dict = {
    "total_trades": 0,
    "profitable_trades": 0,
    "total_profit": 0.0,
    "total_volume": 0.0,
    "opportunities": [],
}


@router.get("", response_model=TradingMetrics)
async def get_metrics() -> TradingMetrics:
    """
    Get trading metrics.

    Returns:
        Current trading metrics
    """
    return TradingMetrics(
        total_trades=_metrics_store["total_trades"],
        profitable_trades=_metrics_store["profitable_trades"],
        total_profit=_metrics_store["total_profit"],
        total_volume=_metrics_store["total_volume"],
        win_rate=(
            _metrics_store["profitable_trades"] / _metrics_store["total_trades"] * 100.0
            if _metrics_store["total_trades"] > 0
            else 0.0
        ),
        active_opportunities=len(_metrics_store["opportunities"]),
    )


@router.get("/opportunities", response_model=List[OpportunityMetrics])
async def get_opportunities() -> List[OpportunityMetrics]:
    """
    Get current arbitrage opportunities.

    Returns:
        List of current opportunities
    """
    return [
        OpportunityMetrics(**opp) for opp in _metrics_store["opportunities"]
    ]


@router.post("/update")
async def update_metrics(metrics: TradingMetrics) -> dict:
    """
    Update metrics (internal use).

    Args:
        metrics: Updated metrics

    Returns:
        Success status
    """
    _metrics_store["total_trades"] = metrics.total_trades
    _metrics_store["profitable_trades"] = metrics.profitable_trades
    _metrics_store["total_profit"] = metrics.total_profit
    _metrics_store["total_volume"] = metrics.total_volume
    return {"status": "updated"}


@router.post("/opportunities/update")
async def update_opportunities(
    opportunities: List[OpportunityMetrics],
) -> dict:
    """
    Update opportunities list (internal use).

    Args:
        opportunities: List of opportunities

    Returns:
        Success status
    """
    _metrics_store["opportunities"] = [opp.dict() for opp in opportunities]
    return {"status": "updated"}

