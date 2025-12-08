import os
import tempfile

import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import text

from app.db.models import Base
from app.db.repository import add_trade, upsert_order


@pytest.mark.asyncio
async def test_db_persist_order_and_trade():
    # Use temporary SQLite database
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_async_engine(f"sqlite+aiosqlite:///{path}")
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        await upsert_order(
            session,
            order_id="test_order",
            exchange="NOBITEX",
            symbol="BTCIRT",
            side="buy",
            order_type="limit",
            status="pending",
            quantity=0.1,
            price=1000000,
        )
        await add_trade(
            session,
            order_id="test_order",
            exchange="NOBITEX",
            symbol="BTCIRT",
            side="buy",
            price=1000000,
            quantity=0.1,
        )

    # Verify data persisted
    async with async_session() as session:
        result = await session.execute(text("SELECT count(*) FROM orders"))
        orders_count = result.scalar_one()
        result = await session.execute(text("SELECT count(*) FROM trades"))
        trades_count = result.scalar_one()

    await engine.dispose()
    os.remove(path)

    assert orders_count == 1
    assert trades_count == 1

