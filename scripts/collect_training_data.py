#!/usr/bin/env python3
"""
Collect real orderbook data from exchanges to build XGBoost training dataset.

How it works:
1. Fetches orderbook snapshots from Nobitex, Wallex, and Invex every N seconds
2. Extracts 19 orderbook features from each snapshot (spread, depth, pressure, etc.)
3. For consecutive snapshot pairs (t, t+delta), generates a label:
   - label=1 (MAKER safe): price was stable enough that a maker order would fill
   - label=0 (use TAKER): price moved too much, maker order would be risky
4. Saves features + labels as CSV for XGBoost training

The labeling logic:
- A maker order sits at the edge of the spread and waits to be filled
- It fills when the market is STABLE (price doesn't move beyond the spread)
- Label = 1 if price change between snapshots < half the spread AND spread didn't widen
- This is legitimate ML: features are from time t, labels are from FUTURE (t+delta)

Usage:
    python scripts/collect_training_data.py                    # Default: 10 min
    python scripts/collect_training_data.py --duration 1800    # 30 minutes
    python scripts/collect_training_data.py --interval 3       # Every 3 seconds
"""

import argparse
import asyncio
import csv
import sys
import time
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.logging import setup_logging, get_logger
setup_logging()

from app.ai.features import extract_orderbook_features
from app.core.config import settings
from app.exchanges.nobitex import NobitexExchange
from app.exchanges.wallex import WallexExchange
from app.exchanges.invex import InvexExchange

logger = get_logger(__name__)


# Exchange configurations: (name, exchange_factory, symbols_to_collect)
EXCHANGE_CONFIGS = [
    ("nobitex", lambda: NobitexExchange(settings.nobitex), ["BTCIRT", "ETHIRT"]),
    ("wallex", lambda: WallexExchange(settings.wallex), ["USDTTMN"]),
    ("invex", lambda: InvexExchange(settings.invex), ["BTC_USDT"]),
]


async def collect_snapshots(
    duration_seconds: int = 600,
    interval_seconds: int = 5,
) -> list[dict]:
    """
    Collect orderbook snapshots from all exchanges.

    Args:
        duration_seconds: How long to collect data (default: 10 minutes)
        interval_seconds: Seconds between snapshots (default: 5)

    Returns:
        List of snapshot dictionaries with features + metadata
    """
    # Initialize exchanges
    exchanges = []
    for name, factory, symbols in EXCHANGE_CONFIGS:
        try:
            exchange = factory()
            exchanges.append((name, exchange, symbols))
            logger.info(f"Initialized {name}")
        except Exception as e:
            logger.warning(f"Failed to initialize {name}: {e}")

    if not exchanges:
        logger.error("No exchanges available!")
        return []

    snapshots = []
    start_time = time.time()
    end_time = start_time + duration_seconds
    round_num = 0
    total_rounds = duration_seconds // interval_seconds

    print(f"\nCollecting orderbook data for {duration_seconds}s "
          f"(interval={interval_seconds}s, ~{total_rounds} rounds)")
    print(f"Exchanges: {[name for name, _, _ in exchanges]}")
    print(f"Started at {datetime.now().strftime('%H:%M:%S')}\n")

    try:
        while time.time() < end_time:
            round_num += 1
            round_start = time.time()
            fetched_count = 0

            for exchange_name, exchange, symbols in exchanges:
                for symbol in symbols:
                    try:
                        ob = await exchange.fetch_orderbook(symbol, depth=10)
                        if ob and ob.bids and ob.asks:
                            features = extract_orderbook_features(ob)
                            snapshot = {
                                "timestamp": time.time(),
                                "exchange": exchange_name,
                                "symbol": symbol,
                                **features,
                            }
                            snapshots.append(snapshot)
                            fetched_count += 1
                    except Exception as e:
                        logger.debug(f"Error fetching {exchange_name}/{symbol}: {e}")

            # Progress indicator
            elapsed = time.time() - start_time
            remaining = max(0, end_time - time.time())
            print(
                f"\r  Round {round_num}/{total_rounds} | "
                f"Fetched: {fetched_count} orderbooks | "
                f"Total snapshots: {len(snapshots)} | "
                f"Remaining: {remaining:.0f}s  ",
                end="", flush=True,
            )

            # Sleep for remaining interval time
            elapsed_this_round = time.time() - round_start
            sleep_time = max(0, interval_seconds - elapsed_this_round)
            if sleep_time > 0 and time.time() < end_time:
                await asyncio.sleep(sleep_time)

    except KeyboardInterrupt:
        print("\n\nCollection interrupted by user.")
    finally:
        # Close exchange connections
        for _, exchange, _ in exchanges:
            try:
                await exchange.close()
            except Exception:
                pass

    print(f"\n\nCollection complete: {len(snapshots)} total snapshots")
    return snapshots


def generate_training_data(snapshots: list[dict]) -> list[dict]:
    """
    Generate labeled training data from consecutive snapshot pairs.

    For each pair of consecutive snapshots (same exchange+symbol):
    - Features come from time t (current market state)
    - Label comes from what happened between t and t+delta (future price movement)

    Adaptive labeling strategy (percentile-based):
    1. First pass: compute price_change and spread_change for ALL pairs
    2. Use the MEDIAN of a composite "volatility score" as threshold
    3. Below median = stable market = maker safe (label=1)
    4. Above median = volatile market = use taker (label=0)

    Why percentile-based (not fixed threshold):
    - Market conditions vary hugely (calm nights vs volatile news events)
    - A fixed threshold creates extreme class imbalance (90/10 or worse)
    - Percentile threshold adapts to actual market conditions during collection
    - Produces balanced classes (~50/50) for robust model training
    - The model learns RELATIVE patterns: "which features predict above-average
      vs below-average price movement?" which generalizes well

    This is legitimate supervised learning because:
    - Features = current observation (no future information leak)
    - Label = future outcome (actual price movement)
    - The percentile threshold is computed ACROSS all data, not per-sample

    Args:
        snapshots: List of collected snapshot dictionaries

    Returns:
        List of training sample dictionaries (features + label)
    """
    # Group snapshots by (exchange, symbol)
    groups: dict[tuple, list[dict]] = {}
    for snap in snapshots:
        key = (snap["exchange"], snap["symbol"])
        groups.setdefault(key, []).append(snap)

    # First pass: collect all (features, volatility_score) pairs
    raw_samples = []

    for (exchange, symbol), group_snapshots in groups.items():
        group_snapshots.sort(key=lambda x: x["timestamp"])

        for i in range(len(group_snapshots) - 1):
            current = group_snapshots[i]
            next_snap = group_snapshots[i + 1]

            # Skip if too much time gap (>30 seconds means we missed rounds)
            time_gap = next_snap["timestamp"] - current["timestamp"]
            if time_gap > 30:
                continue

            mid_price_t = current["mid_price"]
            mid_price_next = next_snap["mid_price"]
            spread_pct_t = current["spread_percent"]
            spread_pct_next = next_snap["spread_percent"]

            if mid_price_t <= 0 or mid_price_next <= 0 or spread_pct_t <= 0:
                continue

            # Compute volatility score: how much did the market move?
            # This combines price change and spread change into one score
            price_change_pct = abs(mid_price_next - mid_price_t) / mid_price_t * 100
            spread_change_ratio = spread_pct_next / spread_pct_t if spread_pct_t > 0 else 1.0

            # Volatility score: higher = more volatile = worse for maker
            # Price change normalized by spread gives "did price move beyond the spread?"
            # Spread widening ratio captures market uncertainty
            volatility_score = (price_change_pct / spread_pct_t) + max(0, spread_change_ratio - 1.0)

            feature_keys = [k for k in current.keys()
                          if k not in ("timestamp", "exchange", "symbol")]
            features = {k: current[k] for k in feature_keys}

            raw_samples.append((features, volatility_score))

    if not raw_samples:
        print("No valid sample pairs generated!")
        return []

    # Second pass: use median volatility as threshold for balanced labels
    scores = [s[1] for s in raw_samples]
    median_score = sorted(scores)[len(scores) // 2]

    print(f"\n  Volatility score stats: min={min(scores):.4f}, "
          f"median={median_score:.4f}, max={max(scores):.4f}")

    training_data = []
    for features, score in raw_samples:
        # Below median volatility = stable = maker safe (1)
        # Above median volatility = volatile = use taker (0)
        label = 1 if score <= median_score else 0
        sample = {**features, "label": label}
        training_data.append(sample)

    # Report label distribution
    if training_data:
        n_maker = sum(1 for s in training_data if s["label"] == 1)
        n_taker = len(training_data) - n_maker
        print(f"  Label distribution: maker={n_maker} ({n_maker/len(training_data)*100:.1f}%), "
              f"taker={n_taker} ({n_taker/len(training_data)*100:.1f}%)")

    return training_data


def save_training_csv(training_data: list[dict], output_path: str) -> None:
    """Save training data to CSV file."""
    if not training_data:
        print("No training data to save!")
        return

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    # Get all feature names (consistent order)
    all_keys = sorted(training_data[0].keys())
    # Ensure 'label' is last column
    if "label" in all_keys:
        all_keys.remove("label")
        all_keys.append("label")

    with open(output, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=all_keys)
        writer.writeheader()
        writer.writerows(training_data)

    print(f"\nSaved {len(training_data)} training samples to {output}")
    print(f"Features: {len(all_keys) - 1} columns + 1 label column")


async def main():
    parser = argparse.ArgumentParser(
        description="Collect orderbook data for XGBoost training"
    )
    parser.add_argument(
        "--duration", type=int, default=600,
        help="Collection duration in seconds (default: 600 = 10 min)"
    )
    parser.add_argument(
        "--interval", type=int, default=5,
        help="Seconds between snapshots (default: 5)"
    )
    parser.add_argument(
        "--output", type=str, default="data/training_data.csv",
        help="Output CSV path (default: data/training_data.csv)"
    )
    args = parser.parse_args()

    print("=" * 60)
    print("ORDERBOOK DATA COLLECTION FOR XGBOOST TRAINING")
    print(f"Duration: {args.duration}s | Interval: {args.interval}s")
    print(f"Output: {args.output}")
    print("=" * 60)

    # Step 1: Collect snapshots
    snapshots = await collect_snapshots(args.duration, args.interval)

    if len(snapshots) < 10:
        print(f"\nInsufficient data collected ({len(snapshots)} snapshots). "
              "Need at least 10. Check exchange connections.")
        return

    # Step 2: Generate labeled training data
    print("\nGenerating training labels from consecutive snapshots...")
    training_data = generate_training_data(snapshots)

    if not training_data:
        print("Failed to generate training data!")
        return

    # Step 3: Save to CSV
    save_training_csv(training_data, args.output)

    print(f"\nDone! Next step: python scripts/train_model.py")


if __name__ == "__main__":
    asyncio.run(main())
