"""Database models for persistence."""

from __future__ import annotations

import datetime as dt
from typing import Optional

from sqlalchemy import DateTime, Enum, Float, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base declarative class."""


class OrderRecord(Base):
    """Stored order information."""

    __tablename__ = "orders"
    __table_args__ = (
        UniqueConstraint("order_id", "exchange", name="uq_orders_order_exchange"),
        Index("idx_orders_exchange_symbol", "exchange", "symbol"),
        Index("idx_orders_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[str] = mapped_column(String(128), nullable=False)
    exchange: Mapped[str] = mapped_column(String(32), nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    side: Mapped[str] = mapped_column(String(8), nullable=False)  # buy/sell
    order_type: Mapped[str] = mapped_column(String(16), nullable=False)  # market/limit
    status: Mapped[str] = mapped_column(String(16), nullable=False)  # pending/filled/cancelled
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    filled_quantity: Mapped[float] = mapped_column(Float, nullable=True)
    price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    fee: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    fee_currency: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    average_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    cost: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: dt.datetime.now(dt.timezone.utc), nullable=False
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: dt.datetime.now(dt.timezone.utc),
        onupdate=lambda: dt.datetime.now(dt.timezone.utc),
        nullable=False,
    )
    exchange_order_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    error: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)


class TradeRecord(Base):
    """Stored trade/fill information."""

    __tablename__ = "trades"
    __table_args__ = (
        Index("idx_trades_exchange_symbol", "exchange", "symbol"),
        Index("idx_trades_timestamp", "timestamp"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trade_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    order_id: Mapped[str] = mapped_column(String(128), nullable=False)
    exchange: Mapped[str] = mapped_column(String(32), nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    fee: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    fee_currency: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    realized_pnl: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    timestamp: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: dt.datetime.now(dt.timezone.utc), nullable=False
    )
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: dt.datetime.now(dt.timezone.utc), nullable=False
    )

