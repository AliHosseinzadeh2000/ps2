"""Risk management API endpoints."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Optional

from app.api.services import get_order_executor
from app.core.logging import get_logger
from app.core.config import settings

logger = get_logger(__name__)
router = APIRouter(prefix="/risk", tags=["risk"])


class RiskMetricsResponse(BaseModel):
    """Risk metrics response model."""
    
    daily_profit_loss: float
    total_position: float
    exchange_positions: Dict[str, float]
    drawdown_percent: float
    avg_slippage_percent: float
    max_slippage_percent: float
    trading_halted: bool
    limits: Dict[str, float]


class TradingHaltRequest(BaseModel):
    """Request to halt/resume trading."""
    
    halted: bool


@router.get("/metrics", response_model=RiskMetricsResponse)
async def get_risk_metrics() -> RiskMetricsResponse:
    """
    Get current risk management metrics.
    
    Returns:
        Risk metrics including P&L, positions, drawdown, slippage
    """
    try:
        executor = get_order_executor()
        metrics = executor.get_risk_metrics()
        
        # Add limit information
        limits = {
            "daily_loss_limit": executor.config.daily_loss_limit,
            "per_trade_loss_limit": executor.config.per_trade_loss_limit,
            "max_position_per_exchange": executor.config.max_position_per_exchange,
            "max_total_position": executor.config.max_total_position,
            "max_drawdown_percent": executor.config.max_drawdown_percent,
            "max_slippage_percent": executor.config.max_slippage_percent,
        }
        
        return RiskMetricsResponse(
            daily_profit_loss=metrics["daily_profit_loss"],
            total_position=metrics["total_position"],
            exchange_positions=metrics["exchange_positions"],
            drawdown_percent=metrics["drawdown_percent"],
            avg_slippage_percent=metrics["avg_slippage_percent"],
            max_slippage_percent=metrics["max_slippage_percent"],
            trading_halted=metrics["trading_halted"],
            limits=limits,
        )
    except Exception as e:
        logger.error(f"Error getting risk metrics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get risk metrics: {str(e)}")


@router.post("/halt", response_model=Dict[str, bool])
async def halt_trading(request: TradingHaltRequest) -> Dict[str, bool]:
    """
    Halt or resume trading.
    
    Args:
        request: Trading halt request
        
    Returns:
        Current halt status
    """
    try:
        executor = get_order_executor()
        executor.config.trading_halted = request.halted
        
        action = "halted" if request.halted else "resumed"
        logger.info(f"Trading {action} via API")
        
        return {"trading_halted": executor.config.trading_halted}
    except Exception as e:
        logger.error(f"Error halting/resuming trading: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to halt/resume trading: {str(e)}")


@router.get("/halt", response_model=Dict[str, bool])
async def get_trading_halt_status() -> Dict[str, bool]:
    """
    Get current trading halt status.
    
    Returns:
        Current halt status
    """
    try:
        executor = get_order_executor()
        return {"trading_halted": executor.config.trading_halted}
    except Exception as e:
        logger.error(f"Error getting halt status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get halt status: {str(e)}")


@router.post("/reset", response_model=Dict[str, str])
async def reset_risk_tracking() -> Dict[str, str]:
    """
    Reset daily risk tracking (P&L, positions, slippage history).
    
    Returns:
        Confirmation message
    """
    try:
        executor = get_order_executor()
        executor.reset_daily_tracking()
        
        logger.info("Risk tracking reset via API")
        return {"message": "Risk tracking reset successfully"}
    except Exception as e:
        logger.error(f"Error resetting risk tracking: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to reset risk tracking: {str(e)}")

