"""Arbitrage opportunity detection engine."""

from dataclasses import dataclass
from typing import Dict, Optional, Union

from app.core.exchange_types import ExchangeName

from app.ai.features import combine_features, extract_orderbook_features
from app.core.config import TradingConfig
from app.data.collector import DataCollector
from app.exchanges.base import ExchangeInterface, OrderBook
from app.utils.math import (
    calculate_arbitrage_profit,
    calculate_spread_percent,
    calculate_required_quantity,
)


@dataclass
class ArbitrageOpportunity:
    """Represents an arbitrage opportunity."""

    symbol: str
    buy_exchange: str
    sell_exchange: str
    buy_price: float
    sell_price: float
    spread_percent: float
    max_quantity: float
    net_profit: float
    profit_percent: float
    buy_fee: float
    sell_fee: float


class ArbitrageEngine:
    """Engine for detecting arbitrage opportunities between exchanges."""

    def __init__(
        self,
        exchanges: Dict[str, ExchangeInterface],
        config: Optional[TradingConfig] = None,
        data_collector: Optional[DataCollector] = None,
    ) -> None:
        """
        Initialize arbitrage engine.

        Args:
            exchanges: Dictionary mapping exchange names to ExchangeInterface instances
            config: Trading configuration
            data_collector: Optional data collector for storing features
        """
        self.exchanges = exchanges
        self.config = config or TradingConfig()
        self.data_collector = data_collector
        self.opportunities: list[ArbitrageOpportunity] = []
        self._latest_orderbooks: dict[str, dict[str, OrderBook]] = {}

    def detect_opportunity(
        self,
        symbol: str,
        buy_exchange_name: str,
        sell_exchange_name: str,
        buy_orderbook: OrderBook,
        sell_orderbook: OrderBook,
    ) -> Optional[ArbitrageOpportunity]:
        """
        Detect arbitrage opportunity between two exchanges.

        Args:
            symbol: Trading pair symbol
            buy_exchange_name: Name of exchange to buy from
            sell_exchange_name: Name of exchange to sell to
            buy_orderbook: Order book from buy exchange
            sell_orderbook: Order book from sell exchange

        Returns:
            ArbitrageOpportunity if profitable, None otherwise
        """
        # Handle both enum and string exchange names
        if isinstance(buy_exchange_name, ExchangeName):
            buy_exchange = self.exchanges.get(buy_exchange_name)
        else:
            # Convert string to enum for lookup
            try:
                buy_exchange_enum = ExchangeName.from_string(buy_exchange_name)
                buy_exchange = self.exchanges.get(buy_exchange_enum)
            except ValueError:
                buy_exchange = None
        
        if isinstance(sell_exchange_name, ExchangeName):
            sell_exchange = self.exchanges.get(sell_exchange_name)
        else:
            # Convert string to enum for lookup
            try:
                sell_exchange_enum = ExchangeName.from_string(sell_exchange_name)
                sell_exchange = self.exchanges.get(sell_exchange_enum)
            except ValueError:
                sell_exchange = None

        if not buy_exchange or not sell_exchange:
            return None

        # Get best prices (lowest ask to buy, highest bid to sell)
        if not buy_orderbook.asks or not sell_orderbook.bids:
            return None

        buy_price = buy_orderbook.asks[0].price
        sell_price = sell_orderbook.bids[0].price

        # Check if profitable
        if sell_price <= buy_price:
            return None

        # Calculate spread
        spread_percent = calculate_spread_percent(buy_price, sell_price)

        # Check minimum spread threshold
        if spread_percent < self.config.min_spread_percent:
            return None

        # Get fees
        buy_fee = buy_exchange.get_taker_fee()  # Initially taker-taker
        sell_fee = sell_exchange.get_taker_fee()

        # Calculate maximum quantity based on available liquidity
        buy_quantity = buy_orderbook.asks[0].quantity
        sell_quantity = sell_orderbook.bids[0].quantity
        max_quantity = min(buy_quantity, sell_quantity)

        # Calculate profit
        net_profit, profit_percent = calculate_arbitrage_profit(
            buy_price,
            sell_price,
            max_quantity,
            buy_fee,
            sell_fee,
        )

        # Check minimum profit threshold
        if net_profit < self.config.min_profit_usdt:
            return None

        # Check maximum position size
        position_value = buy_price * max_quantity
        if position_value > self.config.max_position_size_usdt:
            max_quantity = calculate_required_quantity(
                self.config.max_position_size_usdt,
                buy_price,
                buy_fee,
            )

            # Recalculate profit with adjusted quantity
            net_profit, profit_percent = calculate_arbitrage_profit(
                buy_price,
                sell_price,
                max_quantity,
                buy_fee,
                sell_fee,
            )

        opportunity = ArbitrageOpportunity(
            symbol=symbol,
            buy_exchange=buy_exchange_name,
            sell_exchange=sell_exchange_name,
            buy_price=buy_price,
            sell_price=sell_price,
            spread_percent=spread_percent,
            max_quantity=max_quantity,
            net_profit=net_profit,
            profit_percent=profit_percent,
            buy_fee=buy_fee,
            sell_fee=sell_fee,
        )

        # Extract and store features for continuous learning
        if self.data_collector:
            try:
                buy_features = extract_orderbook_features(buy_orderbook)
                sell_features = extract_orderbook_features(sell_orderbook)
                # Features are stored in memory and will be saved when trade completes
            except Exception:
                # Don't fail opportunity detection if feature extraction fails
                pass

        return opportunity

    def find_opportunities(
        self,
        symbol: str,
        orderbooks: dict[str, OrderBook],
    ) -> list[ArbitrageOpportunity]:
        """
        Find all arbitrage opportunities for a symbol across exchanges.

        Args:
            symbol: Trading pair symbol
            orderbooks: Dictionary mapping exchange names to order books

        Returns:
            List of arbitrage opportunities
        """
        opportunities = []
        exchange_names = list(orderbooks.keys())

        # Check all pairs of exchanges
        for i, buy_exchange_name in enumerate(exchange_names):
            for sell_exchange_name in exchange_names[i + 1 :]:
                # Handle both enum and string keys
                buy_key = buy_exchange_name.value if isinstance(buy_exchange_name, ExchangeName) else buy_exchange_name
                sell_key = sell_exchange_name.value if isinstance(sell_exchange_name, ExchangeName) else sell_exchange_name
                
                buy_orderbook = orderbooks.get(buy_key)
                sell_orderbook = orderbooks.get(sell_key)
                
                if not buy_orderbook or not sell_orderbook:
                    continue

                # Try buy on first exchange, sell on second
                opp1 = self.detect_opportunity(
                    symbol,
                    buy_exchange_name,
                    sell_exchange_name,
                    buy_orderbook,
                    sell_orderbook,
                )
                if opp1:
                    opportunities.append(opp1)

                # Try buy on second exchange, sell on first
                opp2 = self.detect_opportunity(
                    symbol,
                    sell_exchange_name,
                    buy_exchange_name,
                    sell_orderbook,
                    buy_orderbook,
                )
                if opp2:
                    opportunities.append(opp2)

        # Sort by profit (descending)
        opportunities.sort(key=lambda x: x.net_profit, reverse=True)
        self.opportunities = opportunities

        return opportunities

    def on_price_update(self, symbol: str, orderbooks: dict[str, OrderBook]) -> None:
        """
        Callback for price stream updates - automatically detect opportunities.

        Args:
            symbol: Trading pair symbol
            orderbooks: Dictionary mapping exchange names to order books
        """
        self._latest_orderbooks[symbol] = orderbooks
        # Automatically find opportunities when orderbooks update
        opportunities = self.find_opportunities(symbol, orderbooks)
        if opportunities:
            logger.info(
                f"Found {len(opportunities)} opportunities for {symbol} "
                f"(best profit: {opportunities[0].net_profit:.2f})"
            )

    def filter_opportunities(
        self,
        opportunities: list[ArbitrageOpportunity],
    ) -> list[ArbitrageOpportunity]:
        """
        Filter opportunities based on criteria.

        Args:
            opportunities: List of opportunities to filter

        Returns:
            Filtered list of opportunities
        """
        filtered = []

        for opp in opportunities:
            if (
                opp.spread_percent >= self.config.min_spread_percent
                and opp.net_profit >= self.config.min_profit_usdt
            ):
                filtered.append(opp)

        return filtered

