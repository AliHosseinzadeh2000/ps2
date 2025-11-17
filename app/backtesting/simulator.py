"""Backtesting simulator for arbitrage strategies."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from app.backtesting.loader import DataLoader
from app.core.logging import get_logger
from app.exchanges.base import OrderBook
from app.strategy.arbitrage_engine import ArbitrageEngine, ArbitrageOpportunity
from app.utils.math import calculate_arbitrage_profit, calculate_fee_amount

logger = get_logger(__name__)


@dataclass
class Trade:
    """Represents a simulated trade."""

    timestamp: float
    symbol: str
    buy_exchange: str
    sell_exchange: str
    quantity: float
    buy_price: float
    sell_price: float
    buy_fee: float
    sell_fee: float
    net_profit: float
    is_maker_buy: bool = False
    is_maker_sell: bool = False


@dataclass
class BacktestResult:
    """Results from a backtest run."""

    total_trades: int = 0
    profitable_trades: int = 0
    total_profit: float = 0.0
    total_volume: float = 0.0
    total_fees_paid: float = 0.0
    total_fees_saved: float = 0.0  # Savings from using maker orders
    trades: List[Trade] = field(default_factory=list)
    max_drawdown: float = 0.0
    win_rate: float = 0.0


class BacktestSimulator:
    """Simulator for backtesting arbitrage strategies."""

    def __init__(
        self,
        arbitrage_engine: ArbitrageEngine,
        initial_balance: float = 10000.0,
    ) -> None:
        """
        Initialize backtest simulator.

        Args:
            arbitrage_engine: ArbitrageEngine instance
            initial_balance: Starting balance in USDT
        """
        self.engine = arbitrage_engine
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.result = BacktestResult()

    def simulate(
        self,
        orderbooks: Dict[str, List[OrderBook]],
        use_maker_orders: bool = False,
        min_profit_threshold: float = 1.0,
    ) -> BacktestResult:
        """
        Simulate trading on historical orderbook data.

        Args:
            orderbooks: Dictionary mapping exchange names to lists of OrderBook objects
            use_maker_orders: Whether to use maker orders (post-only)
            min_profit_threshold: Minimum profit to execute trade

        Returns:
            BacktestResult object
        """
        self.balance = self.initial_balance
        self.result = BacktestResult()

        # Find minimum length across all exchanges
        exchange_names = list(orderbooks.keys())
        if not exchange_names:
            logger.warning("No orderbook data provided")
            return self.result

        min_length = min(len(orderbooks[ex]) for ex in exchange_names)

        logger.info(
            f"Starting backtest with {min_length} time steps across "
            f"{len(exchange_names)} exchanges"
        )

        # Process each time step
        for i in range(min_length):
            # Get orderbooks for current time step
            current_orderbooks = {
                ex: orderbooks[ex][i] for ex in exchange_names
            }

            # Get symbol from first orderbook
            symbol = current_orderbooks[exchange_names[0]].symbol

            # Find opportunities
            opportunities = self.engine.find_opportunities(symbol, current_orderbooks)

            # Execute best opportunity if profitable
            if opportunities:
                best_opp = opportunities[0]

                if best_opp.net_profit >= min_profit_threshold:
                    # Check if we have enough balance
                    required_capital = best_opp.buy_price * best_opp.max_quantity * (
                        1 + best_opp.buy_fee
                    )

                    if self.balance >= required_capital:
                        trade = self._execute_trade(
                            best_opp,
                            current_orderbooks[best_opp.buy_exchange].timestamp,
                            use_maker_orders,
                        )
                        self.result.trades.append(trade)
                        self.result.total_trades += 1

                        if trade.net_profit > 0:
                            self.result.profitable_trades += 1
                            self.balance += trade.net_profit

                        self.result.total_profit += trade.net_profit
                        self.result.total_volume += (
                            best_opp.buy_price * best_opp.max_quantity
                        )

        # Calculate final metrics
        self._calculate_metrics()

        logger.info(
            f"Backtest complete: {self.result.total_trades} trades, "
            f"{self.result.profitable_trades} profitable, "
            f"Total profit: {self.result.total_profit:.2f} USDT"
        )

        return self.result

    def _execute_trade(
        self,
        opportunity: ArbitrageOpportunity,
        timestamp: float,
        use_maker: bool,
    ) -> Trade:
        """
        Execute a simulated trade.

        Args:
            opportunity: Arbitrage opportunity
            timestamp: Trade timestamp
            use_maker: Whether to use maker orders

        Returns:
            Trade object
        """
        # Determine fees based on order type
        buy_fee = (
            self.engine.exchanges[opportunity.buy_exchange].get_maker_fee()
            if use_maker
            else opportunity.buy_fee
        )
        sell_fee = (
            self.engine.exchanges[opportunity.sell_exchange].get_maker_fee()
            if use_maker
            else opportunity.sell_fee
        )

        # Calculate fees
        buy_fee_amount = calculate_fee_amount(
            opportunity.buy_price, opportunity.max_quantity, buy_fee
        )
        sell_fee_amount = calculate_fee_amount(
            opportunity.sell_price, opportunity.max_quantity, sell_fee
        )

        # Calculate net profit with actual fees
        net_profit, _ = calculate_arbitrage_profit(
            opportunity.buy_price,
            opportunity.sell_price,
            opportunity.max_quantity,
            buy_fee,
            sell_fee,
        )

        # Calculate fee savings (compared to taker-taker)
        taker_fee_buy = self.engine.exchanges[
            opportunity.buy_exchange
        ].get_taker_fee()
        taker_fee_sell = self.engine.exchanges[
            opportunity.sell_exchange
        ].get_taker_fee()

        taker_buy_fee_amount = calculate_fee_amount(
            opportunity.buy_price, opportunity.max_quantity, taker_fee_buy
        )
        taker_sell_fee_amount = calculate_fee_amount(
            opportunity.sell_price, opportunity.max_quantity, taker_fee_sell
        )

        fee_savings = (
            (taker_buy_fee_amount + taker_sell_fee_amount)
            - (buy_fee_amount + sell_fee_amount)
        )

        trade = Trade(
            timestamp=timestamp,
            symbol=opportunity.symbol,
            buy_exchange=opportunity.buy_exchange,
            sell_exchange=opportunity.sell_exchange,
            quantity=opportunity.max_quantity,
            buy_price=opportunity.buy_price,
            sell_price=opportunity.sell_price,
            buy_fee=buy_fee,
            sell_fee=sell_fee,
            net_profit=net_profit,
            is_maker_buy=use_maker,
            is_maker_sell=use_maker,
        )

        self.result.total_fees_paid += buy_fee_amount + sell_fee_amount
        self.result.total_fees_saved += fee_savings

        return trade

    def _calculate_metrics(self) -> None:
        """Calculate final backtest metrics."""
        if self.result.total_trades == 0:
            return

        self.result.win_rate = (
            self.result.profitable_trades / self.result.total_trades * 100.0
        )

        # Calculate max drawdown
        if self.result.trades:
            cumulative_profit = 0.0
            peak = 0.0
            max_dd = 0.0

            for trade in self.result.trades:
                cumulative_profit += trade.net_profit
                if cumulative_profit > peak:
                    peak = cumulative_profit
                drawdown = peak - cumulative_profit
                if drawdown > max_dd:
                    max_dd = drawdown

            self.result.max_drawdown = max_dd

    def get_summary(self) -> Dict:
        """
        Get summary of backtest results.

        Returns:
            Dictionary with summary statistics
        """
        return {
            "initial_balance": self.initial_balance,
            "final_balance": self.initial_balance + self.result.total_profit,
            "total_profit": self.result.total_profit,
            "total_trades": self.result.total_trades,
            "profitable_trades": self.result.profitable_trades,
            "win_rate": self.result.win_rate,
            "total_volume": self.result.total_volume,
            "total_fees_paid": self.result.total_fees_paid,
            "total_fees_saved": self.result.total_fees_saved,
            "max_drawdown": self.result.max_drawdown,
            "roi_percent": (
                self.result.total_profit / self.initial_balance * 100.0
                if self.initial_balance > 0
                else 0.0
            ),
        }

