"""Repository helpers for persisting orders and trades."""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import OrderRecord, TradeRecord

logger = logging.getLogger(__name__)


async def upsert_order(
    session: AsyncSession,
    *,
    order_id: str,
    exchange: str,
    symbol: str,
    side: str,
    order_type: str,
    status: str,
    quantity: float,
    filled_quantity: Optional[float] = None,
    price: Optional[float] = None,
    fee: Optional[float] = None,
    fee_currency: Optional[str] = None,
    average_price: Optional[float] = None,
    cost: Optional[float] = None,
    exchange_order_id: Optional[str] = None,
    error: Optional[str] = None,
) -> None:
    """Insert or update an order record."""
    try:
        stmt = select(OrderRecord).where(
            OrderRecord.order_id == order_id,
            OrderRecord.exchange == exchange,
        )
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            for field, value in [
                ("status", status),
                ("filled_quantity", filled_quantity),
                ("price", price),
                ("fee", fee),
                ("fee_currency", fee_currency),
                ("average_price", average_price),
                ("cost", cost),
                ("exchange_order_id", exchange_order_id),
                ("error", error),
            ]:
                if value is not None:
                    setattr(existing, field, value)
            await session.commit()
            return

        record = OrderRecord(
            order_id=order_id,
            exchange=exchange,
            symbol=symbol,
            side=side,
            order_type=order_type,
            status=status,
            quantity=quantity,
            filled_quantity=filled_quantity,
            price=price,
            fee=fee,
            fee_currency=fee_currency,
            average_price=average_price,
            cost=cost,
            exchange_order_id=exchange_order_id,
            error=error,
        )
        session.add(record)
        await session.commit()
    except Exception:
        await session.rollback()
        logger.exception("Failed to upsert order %s on %s", order_id, exchange)


async def add_trade(
    session: AsyncSession,
    *,
    order_id: str,
    exchange: str,
    symbol: str,
    side: str,
    price: Optional[float],
    quantity: float,
    fee: Optional[float] = None,
    fee_currency: Optional[str] = None,
    realized_pnl: Optional[float] = None,
    trade_id: Optional[str] = None,
) -> None:
    """Insert a trade record."""
    try:
        trade = TradeRecord(
            trade_id=trade_id,
            order_id=order_id,
            exchange=exchange,
            symbol=symbol,
            side=side,
            price=price,
            quantity=quantity,
            fee=fee,
            fee_currency=fee_currency,
            realized_pnl=realized_pnl,
        )
        session.add(trade)
        await session.commit()
    except Exception:
        await session.rollback()
        logger.exception("Failed to add trade for order %s on %s", order_id, exchange)

