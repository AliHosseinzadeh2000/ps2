#!/usr/bin/env python3
"""
Compare AI-driven maker/taker strategy vs baseline strategies.

This script demonstrates the impact of the AI model by simulating
three strategies on the same test data:
  1. Always Taker (no AI) - safest, highest fees
  2. Always Maker (naive) - lowest fees, risk of unfilled orders
  3. AI-Driven (our model) - smart fee optimization

It uses the trained XGBoost model and real orderbook data to show:
  - Fee savings per trade
  - Expected fill rates
  - Net profit comparison
  - When the AI chooses maker vs taker and why

Usage:
    python scripts/compare_ai_impact.py
    python scripts/compare_ai_impact.py --data data/training_combined.csv
    python scripts/compare_ai_impact.py --volume 100000000  # custom daily volume (IRR)
"""

import argparse
import json
import pickle
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd


# Fee rates (typical for Iranian exchanges)
TAKER_FEE = 0.0025  # 0.25%
MAKER_FEE = 0.0010  # 0.10%
MAKER_FILL_RATE = 0.70  # estimated 70% fill rate for maker orders


def load_model(model_path: str = "models/xgboost_model.pkl"):
    """Load the trained XGBoost model."""
    with open(model_path, "rb") as f:
        data = pickle.load(f)
    return data["classifier"], data["feature_names"]


def simulate_strategies(
    df: pd.DataFrame,
    model,
    feature_names: list[str],
    daily_volume: float = 100_000_000,
):
    """
    Simulate three strategies on the dataset and compare results.

    Args:
        df: DataFrame with features and labels
        model: Trained XGBoost classifier
        feature_names: Feature column names
        daily_volume: Simulated daily trading volume in IRR

    Returns:
        Dictionary with comparison results
    """
    X = df[feature_names].values
    y_true = df["label"].values  # 1 = maker-safe, 0 = use-taker

    # AI predictions
    y_pred = model.predict(X)
    y_proba = model.predict_proba(X)[:, 1]

    n_samples = len(y_true)
    per_trade_volume = daily_volume / n_samples

    # === Strategy 1: Always Taker ===
    taker_fee_per_trade = per_trade_volume * TAKER_FEE
    taker_total_fees = taker_fee_per_trade * n_samples
    taker_fill_rate = 1.0  # always fills

    # === Strategy 2: Always Maker ===
    maker_fee_per_trade = per_trade_volume * MAKER_FEE
    # Some orders won't fill (taker-labeled moments = volatile market)
    n_would_fail = (y_true == 0).sum()  # ground truth: these needed taker
    n_would_fill = (y_true == 1).sum()
    maker_filled_fees = maker_fee_per_trade * n_would_fill
    # Failed orders need to be retried as taker (extra cost + delay)
    maker_retry_fees = per_trade_volume * TAKER_FEE * n_would_fail
    maker_total_fees = maker_filled_fees + maker_retry_fees
    maker_fill_rate = n_would_fill / n_samples

    # === Strategy 3: AI-Driven ===
    ai_maker_count = (y_pred == 1).sum()
    ai_taker_count = (y_pred == 0).sum()

    # Correct predictions
    true_positives = ((y_pred == 1) & (y_true == 1)).sum()   # AI said maker, was safe
    false_positives = ((y_pred == 1) & (y_true == 0)).sum()  # AI said maker, was risky
    true_negatives = ((y_pred == 0) & (y_true == 0)).sum()   # AI said taker, was risky
    false_negatives = ((y_pred == 0) & (y_true == 1)).sum()  # AI said taker, was safe

    # AI fee calculation:
    # - Correct maker predictions: pay maker fee (0.10%)
    # - Wrong maker predictions (false positive): order might not fill, retry as taker
    # - Taker predictions: pay taker fee (0.25%)
    ai_correct_maker_fees = per_trade_volume * MAKER_FEE * true_positives
    ai_wrong_maker_fees = per_trade_volume * TAKER_FEE * false_positives  # retry cost
    ai_taker_fees = per_trade_volume * TAKER_FEE * (true_negatives + false_negatives)
    ai_total_fees = ai_correct_maker_fees + ai_wrong_maker_fees + ai_taker_fees

    # Savings
    savings_vs_taker = taker_total_fees - ai_total_fees
    savings_vs_maker = maker_total_fees - ai_total_fees
    savings_pct = (savings_vs_taker / taker_total_fees) * 100

    results = {
        "dataset": {
            "total_samples": n_samples,
            "maker_safe_samples": int((y_true == 1).sum()),
            "taker_needed_samples": int((y_true == 0).sum()),
            "maker_ratio": float((y_true == 1).mean()),
        },
        "ai_predictions": {
            "predicted_maker": int(ai_maker_count),
            "predicted_taker": int(ai_taker_count),
            "true_positives": int(true_positives),
            "false_positives": int(false_positives),
            "true_negatives": int(true_negatives),
            "false_negatives": int(false_negatives),
            "accuracy": float((y_pred == y_true).mean()),
            "maker_precision": float(true_positives / ai_maker_count) if ai_maker_count > 0 else 0,
        },
        "strategy_comparison": {
            "daily_volume": daily_volume,
            "always_taker": {
                "daily_fees": round(taker_total_fees),
                "fee_rate": "0.25%",
                "fill_rate": "100%",
                "description": "Safe but expensive",
            },
            "always_maker": {
                "daily_fees": round(maker_total_fees),
                "fee_rate": "0.10% (when fills)",
                "fill_rate": f"{maker_fill_rate*100:.1f}%",
                "description": "Cheap but unreliable",
            },
            "ai_driven": {
                "daily_fees": round(ai_total_fees),
                "effective_fee_rate": f"{(ai_total_fees / daily_volume)*100:.3f}%",
                "fill_rate": f"{((true_positives + true_negatives + false_negatives) / n_samples)*100:.1f}%",
                "description": "Smart balance of cost and reliability",
            },
        },
        "savings": {
            "daily_vs_taker": round(savings_vs_taker),
            "monthly_vs_taker": round(savings_vs_taker * 30),
            "annual_vs_taker": round(savings_vs_taker * 365),
            "percentage_saved": round(savings_pct, 1),
        },
    }

    return results


def print_report(results: dict):
    """Print a formatted comparison report."""
    ds = results["dataset"]
    ai = results["ai_predictions"]
    sc = results["strategy_comparison"]
    sv = results["savings"]

    volume = sc["daily_volume"]
    volume_str = f"{volume:,.0f}"

    print()
    print("=" * 70)
    print("   AI IMPACT ANALYSIS: Maker/Taker Strategy Comparison")
    print("=" * 70)

    print(f"\n--- Dataset ---")
    print(f"  Total samples:      {ds['total_samples']:,}")
    print(f"  Maker-safe moments: {ds['maker_safe_samples']:,} ({ds['maker_ratio']*100:.1f}%)")
    print(f"  Taker-needed:       {ds['taker_needed_samples']:,} ({(1-ds['maker_ratio'])*100:.1f}%)")

    print(f"\n--- AI Model Decisions ---")
    print(f"  Predicted maker: {ai['predicted_maker']:,} times")
    print(f"  Predicted taker: {ai['predicted_taker']:,} times")
    print(f"  Accuracy: {ai['accuracy']*100:.1f}%")
    print(f"  Maker precision: {ai['maker_precision']*100:.1f}% (when AI says maker, it's right this often)")

    print(f"\n--- Fee Comparison (Daily Volume: {volume_str} IRR) ---")
    print(f"  {'Strategy':<25} {'Daily Fees':>15} {'Fee Rate':>12} {'Fill Rate':>10}")
    print(f"  {'-'*25} {'-'*15} {'-'*12} {'-'*10}")

    t = sc["always_taker"]
    print(f"  {'Always Taker (no AI)':<25} {t['daily_fees']:>12,} IRR {t['fee_rate']:>12} {t['fill_rate']:>10}")

    m = sc["always_maker"]
    print(f"  {'Always Maker (naive)':<25} {m['daily_fees']:>12,} IRR {m['fee_rate']:>12} {m['fill_rate']:>10}")

    a = sc["ai_driven"]
    print(f"  {'AI-Driven (our model)':<25} {a['daily_fees']:>12,} IRR {a['effective_fee_rate']:>12} {a['fill_rate']:>10}")

    print(f"\n--- Savings (AI vs Always-Taker) ---")
    print(f"  Daily savings:   {sv['daily_vs_taker']:>12,} IRR ({sv['percentage_saved']}%)")
    print(f"  Monthly savings: {sv['monthly_vs_taker']:>12,} IRR")
    print(f"  Annual savings:  {sv['annual_vs_taker']:>12,} IRR")

    print(f"\n--- Confusion Matrix ---")
    print(f"                        Predicted")
    print(f"                    Taker     Maker")
    print(f"  Actual Taker  [ {ai['true_negatives']:>5}     {ai['false_positives']:>5} ]")
    print(f"  Actual Maker  [ {ai['false_negatives']:>5}     {ai['true_positives']:>5} ]")

    print(f"\n--- Interpretation ---")
    if sv['percentage_saved'] > 0:
        print(f"  The AI model saves {sv['percentage_saved']}% on trading fees compared to always using taker orders.")
        print(f"  It correctly identifies {ai['maker_precision']*100:.0f}% of maker opportunities,")
        print(f"  reducing fees while maintaining high order fill rates.")
    else:
        print(f"  The AI model needs more training data to outperform the taker baseline.")

    print(f"\n  Key insight: The AI doesn't need to be perfect to save money.")
    print(f"  Even with {ai['accuracy']*100:.0f}% accuracy, the fee difference (0.25% vs 0.10%)")
    print(f"  means correct maker predictions generate significant savings.")

    print()
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(
        description="Compare AI-driven vs baseline trading strategies"
    )
    parser.add_argument(
        "--data", type=str, default="data/training_combined.csv",
        help="Path to training data CSV"
    )
    parser.add_argument(
        "--model", type=str, default="models/xgboost_model.pkl",
        help="Path to trained model"
    )
    parser.add_argument(
        "--volume", type=float, default=100_000_000,
        help="Daily trading volume in IRR (default: 100,000,000)"
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Output results as JSON instead of formatted report"
    )
    args = parser.parse_args()

    # Load data
    df = pd.read_csv(args.data)
    print(f"Loaded {len(df)} samples from {args.data}")

    # Load model
    model, feature_names = load_model(args.model)
    print(f"Loaded model from {args.model}")

    # Run simulation
    results = simulate_strategies(df, model, feature_names, args.volume)

    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        print_report(results)

    # Save results
    output_path = "models/ai_impact_comparison.json"
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"Results saved to {output_path}")


if __name__ == "__main__":
    main()
