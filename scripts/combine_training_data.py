#!/usr/bin/env python3
"""
Combine multiple training data CSV files into a single dataset.

This script is used to merge data from multiple collection sessions,
allowing incremental model improvement by accumulating diverse samples.

Usage:
    python scripts/combine_training_data.py data/training_iter1.csv data/training_iter2.csv
    python scripts/combine_training_data.py data/training_*.csv --output data/training_combined.csv
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd


def combine_datasets(input_files: list[str], output_path: str, remove_duplicates: bool = True) -> None:
    """
    Combine multiple training CSV files.

    Args:
        input_files: List of CSV file paths to combine
        output_path: Path to save combined dataset
        remove_duplicates: Whether to remove duplicate samples (default: True)
    """
    if len(input_files) < 2:
        print("Error: Need at least 2 input files to combine")
        sys.exit(1)

    print("=" * 60)
    print("COMBINING TRAINING DATASETS")
    print("=" * 60)

    # Load all datasets
    dataframes = []
    total_samples = 0

    for i, file_path in enumerate(input_files, 1):
        path = Path(file_path)
        if not path.exists():
            print(f"\nError: File not found: {file_path}")
            sys.exit(1)

        df = pd.read_csv(file_path)
        dataframes.append(df)
        total_samples += len(df)

        print(f"\n  Dataset {i}: {path.name}")
        print(f"    - Samples: {len(df)}")
        print(f"    - Features: {len(df.columns) - 1}")  # -1 for label column

        # Show label distribution
        if "label" in df.columns:
            n_maker = (df["label"] == 1).sum()
            n_taker = (df["label"] == 0).sum()
            print(f"    - Maker: {n_maker} ({n_maker/len(df)*100:.1f}%)")
            print(f"    - Taker: {n_taker} ({n_taker/len(df)*100:.1f}%)")

    # Combine all dataframes
    print(f"\n  Combining {len(dataframes)} datasets...")
    combined = pd.concat(dataframes, ignore_index=True)

    print(f"  Total samples before deduplication: {len(combined)}")

    # Remove duplicates if requested
    if remove_duplicates:
        # Drop duplicates based on all feature columns (exclude label from duplicate check)
        feature_cols = [col for col in combined.columns if col != "label"]
        combined = combined.drop_duplicates(subset=feature_cols, keep="first")
        duplicates_removed = total_samples - len(combined)
        print(f"  Duplicates removed: {duplicates_removed}")

    print(f"  Final dataset: {len(combined)} samples")

    # Show combined label distribution
    if "label" in combined.columns:
        n_maker = (combined["label"] == 1).sum()
        n_taker = (combined["label"] == 0).sum()
        print(f"\n  Combined Label Distribution:")
        print(f"    - Maker: {n_maker} ({n_maker/len(combined)*100:.1f}%)")
        print(f"    - Taker: {n_taker} ({n_taker/len(combined)*100:.1f}%)")

    # Save combined dataset
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(output, index=False)

    print(f"\n  Saved to: {output}")
    print(f"  Size: {output.stat().st_size / 1024:.1f} KB")

    print("\n" + "=" * 60)
    print("COMBINATION COMPLETE")
    print("=" * 60)
    print(f"\nNext step: Train model on combined data")
    print(f"  python scripts/train_model.py --data {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Combine multiple training data CSV files"
    )
    parser.add_argument(
        "input_files",
        nargs="+",
        help="Input CSV files to combine (e.g., data/training_iter*.csv)"
    )
    parser.add_argument(
        "--output",
        default="data/training_combined.csv",
        help="Output path for combined dataset (default: data/training_combined.csv)"
    )
    parser.add_argument(
        "--keep-duplicates",
        action="store_true",
        help="Keep duplicate samples (default: remove duplicates)"
    )
    args = parser.parse_args()

    combine_datasets(
        args.input_files,
        args.output,
        remove_duplicates=not args.keep_duplicates
    )


if __name__ == "__main__":
    main()
