#!/usr/bin/env python3
"""Check what's in the database."""

import asyncio
from sqlalchemy import select
from app.db.db import get_session_factory
from app.db.models import OrderRecord, TradeRecord


async def main():
    """Check database contents."""
    factory = get_session_factory()

    async with factory() as session:
        # Check orders
        result = await session.execute(select(OrderRecord))
        orders = result.scalars().all()

        print("=" * 80)
        print(f"ORDERS IN DATABASE: {len(orders)}")
        print("=" * 80)

        for i, order in enumerate(orders, 1):
            print(f"\nOrder {i}:")
            print(f"  ID: {order.order_id}")
            print(f"  Exchange: {order.exchange}")
            print(f"  Symbol: {order.symbol}")
            print(f"  Side: {order.side}")
            print(f"  Type: {order.order_type}")
            print(f"  Status: {order.status}")
            print(f"  Quantity: {order.quantity}")
            print(f"  Price: {order.price}")
            print(f"  Filled: {order.filled_quantity}")
            print(f"  Fee: {order.fee}")
            print(f"  Created: {order.created_at}")
            print(f"  Error: {order.error}")

        # Check trades
        result = await session.execute(select(TradeRecord))
        trades = result.scalars().all()

        print("\n" + "=" * 80)
        print(f"TRADES IN DATABASE: {len(trades)}")
        print("=" * 80)

        for i, trade in enumerate(trades, 1):
            print(f"\nTrade {i}:")
            print(f"  Trade ID: {trade.trade_id}")
            print(f"  Order ID: {trade.order_id}")
            print(f"  Exchange: {trade.exchange}")
            print(f"  Symbol: {trade.symbol}")
            print(f"  Side: {trade.side}")
            print(f"  Price: {trade.price}")
            print(f"  Quantity: {trade.quantity}")
            print(f"  Fee: {trade.fee}")
            print(f"  P&L: {trade.realized_pnl}")
            print(f"  Timestamp: {trade.timestamp}")

        # VERDICT
        print("\n" + "=" * 80)
        print("VERDICT")
        print("=" * 80)

        if len(orders) > 0:
            print(f"✅ Found {len(orders)} order(s)")
            print("\nBUT THE QUESTION IS:")
            print("  - Are these real orders placed on exchanges?")
            print("  - Or test/mock data?")
            print("  - Check the order IDs and statuses above")
        else:
            print("❌ No orders - Bot has NEVER placed an order")

        if len(trades) > 0:
            print(f"\n✅ Found {len(trades)} trade(s)")
            print("   This means orders were FILLED")
        else:
            print("\n❌ No trades - No orders have been filled")

        print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
