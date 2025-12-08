"""Historical data endpoints (read-only)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exchange_types import ExchangeName
from app.db.db import get_session
from app.db.models import OrderRecord, TradeRecord

router = APIRouter(prefix="/history", tags=["history"])


class OrderRecordResponse(BaseModel):
    id: int
    order_id: str
    exchange: str
    symbol: str
    side: str
    order_type: str
    status: str
    quantity: float
    filled_quantity: Optional[float] = None
    price: Optional[float] = None
    fee: Optional[float] = None
    fee_currency: Optional[str] = None
    average_price: Optional[float] = None
    cost: Optional[float] = None
    created_at: str
    updated_at: str
    error: Optional[str] = None

    class Config:
        orm_mode = True


class TradeRecordResponse(BaseModel):
    id: int
    trade_id: Optional[str] = None
    order_id: str
    exchange: str
    symbol: str
    side: str
    price: Optional[float] = None
    quantity: float
    fee: Optional[float] = None
    fee_currency: Optional[str] = None
    realized_pnl: Optional[float] = None
    timestamp: str
    created_at: str

    class Config:
        orm_mode = True


@router.get("/orders", response_model=List[OrderRecordResponse])
async def list_orders(
    exchange: Optional[ExchangeName] = Query(None, description="Filter by exchange"),
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> List[OrderRecordResponse]:
    """List orders with optional filters."""
    try:
        stmt = select(OrderRecord)
        if exchange:
            stmt = stmt.where(OrderRecord.exchange == exchange.value)
        if symbol:
            stmt = stmt.where(OrderRecord.symbol == symbol)
        if status:
            stmt = stmt.where(OrderRecord.status == status)
        stmt = stmt.order_by(OrderRecord.created_at.desc()).offset(offset).limit(limit)

        result = await session.execute(stmt)
        rows = result.scalars().all()
        return rows
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch orders: {e}")


@router.get("/trades", response_model=List[TradeRecordResponse])
async def list_trades(
    exchange: Optional[ExchangeName] = Query(None, description="Filter by exchange"),
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> List[TradeRecordResponse]:
    """List trades with optional filters."""
    try:
        stmt = select(TradeRecord)
        if exchange:
            stmt = stmt.where(TradeRecord.exchange == exchange.value)
        if symbol:
            stmt = stmt.where(TradeRecord.symbol == symbol)
        stmt = stmt.order_by(TradeRecord.timestamp.desc()).offset(offset).limit(limit)

        result = await session.execute(stmt)
        rows = result.scalars().all()
        return rows
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch trades: {e}")

