# Order Tracking and Exchange Management

## Current Implementation

### In-Memory Order Tracking

The bot currently uses **in-memory order tracking** via the `OrderExecutor` class:

```python
class OrderExecutor:
    def __init__(self, ...):
        self.active_orders: dict[str, Order] = {}  # In-memory storage
```

**Characteristics:**
- ✅ Fast and simple
- ✅ No database dependency
- ❌ Orders are lost on restart
- ❌ No historical tracking
- ❌ No recovery from crashes

### How It Works

1. **Order Placement**: When an order is placed, it's stored in `self.active_orders` dictionary
2. **Order Status Polling**: The executor polls exchange APIs to check order status
3. **Order Completion**: Once filled/cancelled, orders remain in memory but are marked as completed

### Exchange Switching

The bot handles multiple exchanges through:

1. **Exchange Dictionary**: All exchanges are stored in a dictionary keyed by `ExchangeName` enum
2. **Symbol Conversion**: Automatically converts symbols between exchanges (e.g., BTCIRT → BTC_IRR)
3. **Unified Interface**: All exchanges implement the same `ExchangeInterface`, so switching is seamless

```python
exchanges = {
    ExchangeName.NOBITEX: NobitexExchange(config),
    ExchangeName.INVEX: InvexExchange(config),
    ExchangeName.WALLEX: WallexExchange(config),
}
```

## Limitations

### What Happens on Restart?

1. **Active Orders**: Lost - the bot doesn't know about orders placed before restart
2. **Order History**: Not persisted - no record of past trades
3. **Risk Tracking**: Reset - daily P&L, positions, etc. start from zero

### What Happens During Runtime?

1. **Order Tracking**: Works fine - orders are tracked in memory
2. **Status Updates**: Polled from exchange APIs
3. **Error Recovery**: Handled via retry logic and circuit breakers

## Production Considerations

### Do You Need a Database?

**For Basic Operation**: **No** - The bot can work without a database because:
- Exchange APIs maintain order state
- You can query exchange APIs for order status
- Risk limits can be recalculated from exchange balances

**For Production/Reliability**: **Yes** - A database would provide:
- ✅ Persistent order history
- ✅ Crash recovery
- ✅ Historical performance analysis
- ✅ Audit trail
- ✅ Better risk management (track across restarts)

### Recommended Approach

#### Option 1: File-Based Storage (Simple)
```python
# Save orders to JSON file periodically
import json
from datetime import datetime

def save_orders(orders: dict):
    with open('orders.json', 'w') as f:
        json.dump(orders, f, default=str)

def load_orders() -> dict:
    try:
        with open('orders.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
```

#### Option 2: SQLite Database (Recommended)
```python
# Lightweight, no external dependencies
import sqlite3

class OrderDatabase:
    def __init__(self, db_path='orders.db'):
        self.conn = sqlite3.connect(db_path)
        self._create_tables()
    
    def _create_tables(self):
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                order_id TEXT PRIMARY KEY,
                exchange TEXT,
                symbol TEXT,
                side TEXT,
                quantity REAL,
                price REAL,
                status TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
        ''')
```

#### Option 3: Full Database (PostgreSQL/MySQL)
- For production systems with high volume
- Better for concurrent access
- Supports complex queries and analytics

## Current Bot Flow (run.sh)

When you run `./run.sh`:

1. **Startup** (`app/api/main.py`):
   ```python
   async def startup_event():
       get_exchanges()  # Initialize all exchanges
       get_arbitrage_engine()  # Initialize arbitrage engine
       get_order_executor()  # Initialize order executor (empty active_orders)
       price_stream.start()  # Start polling orderbooks
   ```

2. **Price Stream**:
   - Continuously polls orderbooks from all exchanges
   - Updates `arbitrage_engine` when prices change
   - Engine detects opportunities automatically

3. **Order Execution**:
   - When opportunity detected, `OrderExecutor.execute_arbitrage()` is called
   - Orders are placed on both exchanges
   - Orders tracked in `executor.active_orders`
   - Status polled until filled/cancelled

4. **Shutdown**:
   - `active_orders` dictionary is lost
   - No persistence (unless you add it)

## Recommendations

### For Testing/Demo (Current State)
✅ **Current implementation is fine** - In-memory tracking works for:
- Testing
- Demonstrations
- Short-running sessions
- Development

### For Production
Consider adding:

1. **Order Persistence**:
   - Save orders to file/database on placement
   - Load orders on startup
   - Query exchange APIs to sync status

2. **Order Recovery**:
   ```python
   async def recover_orders(self):
       """Recover orders from exchange APIs on startup."""
       for exchange_name, exchange in self.exchanges.items():
           if exchange.is_authenticated():
               open_orders = await exchange.get_open_orders()
               for order in open_orders:
                   self.active_orders[order.order_id] = order
   ```

3. **Trade History**:
   - Log all completed trades
   - Track P&L over time
   - Generate reports

## Summary

- **Current**: In-memory tracking, works for testing
- **Exchange Switching**: Handled automatically via unified interface
- **Order Tracking**: Lost on restart, but exchange APIs maintain state
- **Production**: Consider adding database for persistence and recovery

The bot is **functional without a database**, but adding one would improve reliability and provide better tracking for production use.

