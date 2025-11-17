"""Historical data loading for backtesting."""

import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional

from app.core.logging import get_logger
from app.exchanges.base import OrderBook, OrderBookEntry

logger = get_logger(__name__)


class DataLoader:
    """Load historical orderbook and OHLC data for backtesting."""

    def __init__(self, data_dir: Optional[str] = None) -> None:
        """
        Initialize data loader.

        Args:
            data_dir: Directory containing historical data files
        """
        self.data_dir = Path(data_dir) if data_dir else Path("./data")

    def load_orderbook_csv(
        self, file_path: str, symbol: str
    ) -> List[OrderBook]:
        """
        Load orderbook data from CSV file.

        Expected CSV format:
        - timestamp: Unix timestamp
        - bid_price_0, bid_quantity_0, ask_price_0, ask_quantity_0, ...
        - Or: bids (JSON string), asks (JSON string)

        Args:
            file_path: Path to CSV file
            symbol: Trading pair symbol

        Returns:
            List of OrderBook objects in chronological order
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Orderbook file not found: {path}")

        try:
            df = pd.read_csv(path)
            orderbooks = []

            for _, row in df.iterrows():
                timestamp = float(row.get("timestamp", 0))

                # Try to parse bids and asks from JSON columns
                if "bids" in row and "asks" in row:
                    import json

                    bids_data = json.loads(row["bids"]) if isinstance(row["bids"], str) else row["bids"]
                    asks_data = json.loads(row["asks"]) if isinstance(row["asks"], str) else row["asks"]

                    bids = [
                        OrderBookEntry(price=float(b[0]), quantity=float(b[1]))
                        for b in bids_data
                    ]
                    asks = [
                        OrderBookEntry(price=float(a[0]), quantity=float(a[1]))
                        for a in asks_data
                    ]
                else:
                    # Parse from numbered columns (bid_price_0, bid_quantity_0, etc.)
                    bids = []
                    asks = []
                    i = 0

                    while f"bid_price_{i}" in row and f"bid_quantity_{i}" in row:
                        bids.append(
                            OrderBookEntry(
                                price=float(row[f"bid_price_{i}"]),
                                quantity=float(row[f"bid_quantity_{i}"]),
                            )
                        )
                        i += 1

                    i = 0
                    while f"ask_price_{i}" in row and f"ask_quantity_{i}" in row:
                        asks.append(
                            OrderBookEntry(
                                price=float(row[f"ask_price_{i}"]),
                                quantity=float(row[f"ask_quantity_{i}"]),
                            )
                        )
                        i += 1

                orderbook = OrderBook(
                    bids=bids,
                    asks=asks,
                    timestamp=timestamp,
                    symbol=symbol,
                )
                orderbooks.append(orderbook)

            logger.info(f"Loaded {len(orderbooks)} orderbook snapshots from {path}")
            return orderbooks

        except Exception as e:
            logger.error(f"Error loading orderbook data: {e}")
            raise

    def load_ohlc_csv(self, file_path: str) -> pd.DataFrame:
        """
        Load OHLC data from CSV file.

        Expected CSV format:
        - timestamp or datetime column
        - open, high, low, close, volume columns

        Args:
            file_path: Path to CSV file

        Returns:
            DataFrame with OHLC data
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"OHLC file not found: {path}")

        try:
            df = pd.read_csv(file_path)

            # Handle timestamp column
            if "timestamp" in df.columns:
                df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s")
            elif "datetime" in df.columns:
                df["datetime"] = pd.to_datetime(df["datetime"])

            # Ensure required columns exist
            required_cols = ["open", "high", "low", "close", "volume"]
            missing = [col for col in required_cols if col not in df.columns]
            if missing:
                raise ValueError(f"Missing required columns: {missing}")

            # Sort by timestamp
            if "timestamp" in df.columns:
                df = df.sort_values("timestamp")
            elif "datetime" in df.columns:
                df = df.sort_values("datetime")

            logger.info(f"Loaded {len(df)} OHLC records from {path}")
            return df

        except Exception as e:
            logger.error(f"Error loading OHLC data: {e}")
            raise

    def load_multiple_orderbooks(
        self, file_paths: Dict[str, str], symbols: Dict[str, str]
    ) -> Dict[str, List[OrderBook]]:
        """
        Load orderbooks for multiple exchanges.

        Args:
            file_paths: Dictionary mapping exchange names to file paths
            symbols: Dictionary mapping exchange names to symbols

        Returns:
            Dictionary mapping exchange names to lists of OrderBook objects
        """
        orderbooks = {}

        for exchange_name, file_path in file_paths.items():
            symbol = symbols.get(exchange_name, "BTCUSDT")
            orderbooks[exchange_name] = self.load_orderbook_csv(file_path, symbol)

        return orderbooks

    def validate_orderbook_data(self, orderbooks: List[OrderBook]) -> bool:
        """
        Validate orderbook data quality.

        Args:
            orderbooks: List of OrderBook objects

        Returns:
            True if data is valid
        """
        if not orderbooks:
            logger.warning("Empty orderbook list")
            return False

        # Check for consistent timestamps (should be increasing)
        timestamps = [ob.timestamp for ob in orderbooks]
        if timestamps != sorted(timestamps):
            logger.warning("Orderbook timestamps are not in chronological order")

        # Check for empty orderbooks
        empty_count = sum(1 for ob in orderbooks if not ob.bids or not ob.asks)
        if empty_count > 0:
            logger.warning(f"{empty_count} empty orderbooks found")

        return True

