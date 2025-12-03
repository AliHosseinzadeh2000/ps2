# Bot Architecture and Order Management

## Overview

This document explains how the arbitrage trading bot handles order tracking, exchange switching, and state management.

## How the Bot Runs (via `./run.sh`)

### Startup Sequence

1. **API Server Starts** (`app/api/main.py`):
   ```python
   @app.on_event("startup")
   async def startup_event():
       get_exchanges()  # Initialize all exchange connections
       get_arbitrage_engine()  # Initialize opportunity detection
       get_order_executor()  # Initialize order executor (empty state)
       price_stream.start()  # Start continuous orderbook polling
   ```

2. **Price Stream** (`app/strategy/price_stream.py`):
   - Polls orderbooks from all configured exchanges every `polling_interval_seconds`
   - Automatically converts symbols (e.g., BTCIRT → BTC_IRR for Invex)
   - Notifies subscribers (arbitrage engine) when prices update

3. **Arbitrage Engine** (`app/strategy/arbitrage_engine.py`):
   - Receives price updates from price stream
   - Detects arbitrage opportunities automatically
   - Filters opportunities based on:
     - Minimum spread threshold
     - Minimum profit
     - Compatible quote currencies (IRT/IRR/TMN are same, but IRT≠USDT)

4. **Order Execution** (`app/strategy/order_executor.py`):
   - When opportunity detected, executes trades
   - Places orders on both exchanges simultaneously
   - Tracks orders in `self.active_orders` dictionary
   - Polls order status until filled/cancelled

## Order Tracking

### Current Implementation: In-Memory

```python
class OrderExecutor:
    def __init__(self, ...):
        self.active_orders: dict[str, Order] = {}  # Key: order_id, Value: Order object
```

**What's Tracked:**
- Order ID
- Exchange name
- Symbol
- Side (buy/sell)
- Quantity
- Price
- Status (pending/filled/cancelled)
- Filled quantity
- Timestamp

### Exchange Switching

The bot seamlessly switches between exchanges because:

1. **Unified Interface**: All exchanges implement `ExchangeInterface`:
   ```python
   class ExchangeInterface(ABC):
       async def place_order(...) -> Order
       async def cancel_order(...) -> bool
       async def get_order(...) -> Order
       async def get_open_orders(...) -> List[Order]
   ```

2. **Symbol Conversion**: Automatic conversion handles format differences:
   - Nobitex: `BTCIRT`
   - Invex: `BTC_IRR`
   - Wallex: `BTCTMN`
   - All represent the same market (BTC/Iranian Toman)

3. **Exchange Dictionary**: All exchanges stored together:
   ```python
   exchanges = {
       ExchangeName.NOBITEX: NobitexExchange(config),
       ExchangeName.INVEX: InvexExchange(config),
       ExchangeName.WALLEX: WallexExchange(config),
   }
   ```

### What Happens on Restart?

**Current Behavior:**
- ❌ `active_orders` dictionary is empty
- ❌ Bot doesn't know about orders placed before restart
- ✅ Exchange APIs still have the orders
- ✅ You can query exchange APIs to recover orders

**Recovery Strategy:**
The bot can recover orders by querying exchange APIs:

```python
async def recover_orders(self):
    """Recover active orders from exchanges on startup."""
    for exchange_name, exchange in self.exchanges.items():
        if exchange.is_authenticated():
            open_orders = await exchange.get_open_orders()
            for order in open_orders:
                self.active_orders[order.order_id] = order
                logger.info(f"Recovered order {order.order_id} from {exchange_name}")
```

## Do You Need a Database?

### Short Answer: **No, but it helps**

### Why No Database is Needed:

1. **Exchange APIs Maintain State**: Orders exist on exchange servers, not just in bot memory
2. **Query on Demand**: Can always query exchange APIs for order status
3. **Stateless Design**: Bot can restart and query exchanges for current state

### Why a Database Would Help:

1. **Order History**: Track all past trades for analysis
2. **Crash Recovery**: Know about orders immediately on restart
3. **Performance Tracking**: Calculate P&L over time
4. **Audit Trail**: Record of all trading activity
5. **Risk Management**: Track positions across restarts

### Current Trade-offs:

| Feature | Without DB | With DB |
|---------|-----------|---------|
| Order Tracking | ✅ Runtime only | ✅ Persistent |
| Order History | ❌ Lost on restart | ✅ Saved |
| Crash Recovery | ⚠️ Manual query | ✅ Automatic |
| Performance Analysis | ❌ Limited | ✅ Full history |
| Complexity | ✅ Simple | ⚠️ More complex |

## Recommended Approach

### For Testing/Demo (Current):
✅ **Keep current implementation** - Works fine for:
- Testing functionality
- Demonstrations
- Short-running sessions
- Development

### For Production:
Consider adding **lightweight persistence**:

#### Option 1: JSON File (Simplest)
```python
import json
from pathlib import Path

class OrderStorage:
    def __init__(self, file_path='orders.json'):
        self.file_path = Path(file_path)
    
    def save_order(self, order: Order):
        orders = self.load_all()
        orders[order.order_id] = order.dict()
        with open(self.file_path, 'w') as f:
            json.dump(orders, f, default=str)
    
    def load_all(self) -> dict:
        if self.file_path.exists():
            with open(self.file_path, 'r') as f:
                return json.load(f)
        return {}
```

#### Option 2: SQLite (Recommended)
- Lightweight (single file)
- No external dependencies
- SQL queries for analysis
- Easy to backup

#### Option 3: Full Database (PostgreSQL)
- For high-volume production
- Better concurrent access
- Advanced analytics

## Fee Configuration

Fees are configured per exchange in `app/core/config.py`:

- **Nobitex** (Toman market, Level 1):
  - Maker: 0.2% (0.002)
  - Taker: 0.25% (0.0025)

- **Invex** (Toman market):
  - Maker: 0.25% (0.0025)
  - Taker: 0.25% (0.0025)
  - Note: Tether market has different fees (Maker 0.1%, Taker 0.13%)

- **Wallex** (Toman market, Level 1):
  - Maker: 0.25% (0.0025)
  - Taker: 0.3% (0.003)

**Note**: Fees are tiered based on trading volume. Current defaults use Level 1 fees. For higher tiers, you can override via environment variables or config.

## Summary

- **Order Tracking**: In-memory during runtime, lost on restart
- **Exchange Switching**: Automatic via unified interface and symbol conversion
- **Database**: Not required, but helpful for production
- **Recovery**: Can query exchange APIs to recover orders
- **Current State**: Suitable for testing/demo, consider persistence for production

The bot is **fully functional without a database** - orders are tracked in memory during runtime, and exchange APIs maintain the authoritative state. For production use, adding persistence would improve reliability and provide better historical tracking.

