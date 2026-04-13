#!/usr/bin/env python3
"""
Train XGBoost model for maker/taker prediction and produce evaluation metrics.

This script:
1. Loads training data CSV (collected by collect_training_data.py)
2. Trains an XGBoost binary classifier (0=taker, 1=maker)
3. Evaluates with proper ML metrics:
   - Accuracy, Precision, Recall, F1-Score
   - Confusion Matrix
   - ROC-AUC Score
   - Feature Importance Rankings
4. Saves trained model to models/xgboost_model.pkl
5. Generates evaluation report

What the model predicts:
- Input: 19 orderbook features (spread, depth, pressure, volatility, etc.)
- Output: Should we use MAKER order (1) or TAKER order (0)?
- Maker = limit order away from best price (lower fee, might not fill)
- Taker = limit order at best price (higher fee, fills immediately)

Why XGBoost:
- Best algorithm for tabular/structured data (proven in finance)
- Fast inference (~1ms per prediction) for real-time trading
- Provides feature importance (explainability for jury)
- Needs less data than neural networks (works with hundreds of samples)

Usage:
    python scripts/train_model.py                           # Default paths
    python scripts/train_model.py --data data/my_data.csv   # Custom data
    python scripts/train_model.py --no-plots                # Skip plots
"""

import argparse
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split

from app.core.logging import setup_logging, get_logger
setup_logging()

logger = get_logger(__name__)


def load_and_prepare_data(data_path: str) -> tuple[np.ndarray, np.ndarray, list[str]]:
    """
    Load CSV and prepare feature matrix X and label vector y.

    Args:
        data_path: Path to training CSV

    Returns:
        (X, y, feature_names) where X is feature matrix, y is labels
    """
    df = pd.read_csv(data_path)
    print(f"Loaded {len(df)} samples from {data_path}")
    print(f"Columns: {list(df.columns)}")

    # Label column
    if "label" not in df.columns:
        raise ValueError("CSV must have a 'label' column (0=taker, 1=maker)")

    # Feature columns = everything except label
    feature_cols = sorted([c for c in df.columns if c != "label"])
    print(f"Features: {len(feature_cols)} columns")

    X = df[feature_cols].values.astype(np.float32)
    y = df["label"].values.astype(np.int32)

    # Handle NaN/Inf
    X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)

    # Report distribution
    n_maker = (y == 1).sum()
    n_taker = (y == 0).sum()
    print(f"Label distribution: maker={n_maker} ({n_maker/len(y)*100:.1f}%), "
          f"taker={n_taker} ({n_taker/len(y)*100:.1f}%)")

    return X, y, feature_cols


def train_xgboost(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_test: np.ndarray,
    y_test: np.ndarray,
    feature_names: list[str],
) -> xgb.XGBClassifier:
    """
    Train XGBoost classifier with early stopping.

    XGBoost Parameters Explained:
    - max_depth=6: Maximum tree depth (controls complexity; 3-8 is typical)
    - learning_rate=0.1: Step size for each boosting round (lower = more rounds needed)
    - n_estimators=200: Maximum number of trees (early stopping usually stops earlier)
    - subsample=0.8: Use 80% of data per tree (prevents overfitting)
    - colsample_bytree=0.8: Use 80% of features per tree (forces diversity)
    - min_child_weight=3: Minimum samples in a leaf (prevents learning noise)
    - gamma=0.1: Minimum loss reduction for a split (regularization)
    - scale_pos_weight: Balances classes if imbalanced

    Args:
        X_train, y_train: Training data
        X_test, y_test: Test data for early stopping
        feature_names: Feature column names

    Returns:
        Trained XGBClassifier
    """
    # Calculate class weight for imbalanced data
    n_positive = (y_train == 1).sum()
    n_negative = (y_train == 0).sum()
    scale_pos_weight = n_negative / n_positive if n_positive > 0 else 1.0

    model = xgb.XGBClassifier(
        objective="binary:logistic",
        eval_metric="logloss",
        max_depth=6,
        learning_rate=0.1,
        n_estimators=200,
        subsample=0.8,
        colsample_bytree=0.8,
        min_child_weight=3,
        gamma=0.1,
        scale_pos_weight=scale_pos_weight,
        random_state=42,
        verbosity=0,
    )

    print("\nTraining XGBoost classifier...")
    model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        verbose=False,
    )

    # Report early stopping
    best_iteration = getattr(model, "best_iteration", model.n_estimators)
    print(f"Training complete. Best iteration: {best_iteration}")

    return model


def evaluate_model(
    model: xgb.XGBClassifier,
    X_test: np.ndarray,
    y_test: np.ndarray,
    feature_names: list[str],
) -> dict:
    """
    Comprehensive model evaluation with all standard ML metrics.

    Metrics explained:
    - Accuracy: % of correct predictions overall
    - Precision: Of all predicted "maker", how many were actually correct?
    - Recall: Of all actual "maker" cases, how many did we catch?
    - F1-Score: Harmonic mean of precision and recall (balanced metric)
    - ROC-AUC: Area under the ROC curve (0.5=random, 1.0=perfect)
    - Confusion Matrix: Shows true/false positives/negatives

    Args:
        model: Trained classifier
        X_test, y_test: Test data
        feature_names: Feature names for importance

    Returns:
        Dictionary of evaluation metrics
    """
    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]

    # Core metrics
    accuracy = accuracy_score(y_test, y_pred)
    precision = precision_score(y_test, y_pred, zero_division=0)
    recall = recall_score(y_test, y_pred, zero_division=0)
    f1 = f1_score(y_test, y_pred, zero_division=0)
    roc_auc = roc_auc_score(y_test, y_proba)
    cm = confusion_matrix(y_test, y_pred)

    print("\n" + "=" * 60)
    print("MODEL EVALUATION RESULTS")
    print("=" * 60)

    print(f"\n  Accuracy:  {accuracy:.4f}  ({accuracy*100:.1f}%)")
    print(f"  Precision: {precision:.4f}  (of predicted maker, {precision*100:.1f}% correct)")
    print(f"  Recall:    {recall:.4f}  (of actual maker, caught {recall*100:.1f}%)")
    print(f"  F1-Score:  {f1:.4f}  (harmonic mean of precision & recall)")
    print(f"  ROC-AUC:   {roc_auc:.4f}  (0.5=random, 1.0=perfect)")

    print(f"\n  Confusion Matrix:")
    print(f"                    Predicted")
    print(f"                  Taker  Maker")
    print(f"  Actual Taker  [ {cm[0][0]:5d}  {cm[0][1]:5d} ]")
    print(f"  Actual Maker  [ {cm[1][0]:5d}  {cm[1][1]:5d} ]")

    # Detailed classification report
    print(f"\n  Classification Report:")
    report = classification_report(y_test, y_pred, target_names=["Taker", "Maker"])
    for line in report.split("\n"):
        print(f"  {line}")

    # Feature importance
    importance = model.feature_importances_
    importance_pairs = sorted(
        zip(feature_names, importance), key=lambda x: x[1], reverse=True
    )

    print("\n  Top 10 Most Important Features:")
    print("  " + "-" * 45)
    for i, (name, imp) in enumerate(importance_pairs[:10], 1):
        bar = "#" * int(imp * 50)
        print(f"  {i:2d}. {name:<25s} {imp:.4f} {bar}")

    # Explain what top features mean
    print("\n  Feature Importance Interpretation:")
    top_feature = importance_pairs[0][0]
    explanations = {
        "spread_percent": "Spread tightness is the key predictor - tight spreads favor maker orders",
        "spread": "Absolute spread drives maker fill probability",
        "depth_imbalance": "Bid/ask volume imbalance predicts short-term price direction",
        "buy_pressure": "Buy-side pressure indicates demand stability",
        "sell_pressure": "Sell-side pressure indicates supply stability",
        "pressure_ratio": "Buy/sell pressure ratio predicts order flow direction",
        "bid_depth": "Bid-side liquidity depth affects maker fill probability",
        "ask_depth": "Ask-side liquidity depth affects market stability",
        "bid_price_std": "Bid price volatility - lower = safer for maker",
        "ask_price_std": "Ask price volatility - lower = safer for maker",
        "spread_percent": "Percentage spread - primary indicator of maker profitability",
        "mid_price": "Mid price captures different market regimes",
    }
    if top_feature in explanations:
        print(f"  -> {explanations[top_feature]}")

    metrics = {
        "accuracy": float(accuracy),
        "precision": float(precision),
        "recall": float(recall),
        "f1_score": float(f1),
        "roc_auc": float(roc_auc),
        "confusion_matrix": cm.tolist(),
        "feature_importance": {name: float(imp) for name, imp in importance_pairs},
        "n_test_samples": len(y_test),
    }

    return metrics


def cross_validate(
    X: np.ndarray, y: np.ndarray, n_folds: int = 5
) -> dict:
    """
    Perform k-fold cross-validation for robust evaluation.

    Cross-validation explained:
    - Splits data into k folds
    - Trains on k-1 folds, tests on remaining fold
    - Repeats k times, each fold is test once
    - Reports mean +/- std of metrics
    - More reliable than single train/test split

    Args:
        X, y: Full dataset
        n_folds: Number of CV folds

    Returns:
        Cross-validation results
    """
    print(f"\n{'='*60}")
    print(f"CROSS-VALIDATION ({n_folds}-fold)")
    print(f"{'='*60}")

    n_positive = (y == 1).sum()
    n_negative = (y == 0).sum()
    scale_pos_weight = n_negative / n_positive if n_positive > 0 else 1.0

    model = xgb.XGBClassifier(
        objective="binary:logistic",
        eval_metric="logloss",
        max_depth=6,
        learning_rate=0.1,
        n_estimators=100,
        subsample=0.8,
        colsample_bytree=0.8,
        min_child_weight=3,
        gamma=0.1,
        scale_pos_weight=scale_pos_weight,
        random_state=42,
        verbosity=0,
    )

    cv = StratifiedKFold(n_splits=n_folds, shuffle=True, random_state=42)

    # Accuracy scores
    accuracy_scores = cross_val_score(model, X, y, cv=cv, scoring="accuracy")
    f1_scores = cross_val_score(model, X, y, cv=cv, scoring="f1")
    roc_auc_scores = cross_val_score(model, X, y, cv=cv, scoring="roc_auc")

    print(f"\n  Accuracy:  {accuracy_scores.mean():.4f} +/- {accuracy_scores.std():.4f}")
    print(f"  F1-Score:  {f1_scores.mean():.4f} +/- {f1_scores.std():.4f}")
    print(f"  ROC-AUC:   {roc_auc_scores.mean():.4f} +/- {roc_auc_scores.std():.4f}")

    print(f"\n  Per-fold accuracy: {[f'{s:.3f}' for s in accuracy_scores]}")

    return {
        "cv_accuracy_mean": float(accuracy_scores.mean()),
        "cv_accuracy_std": float(accuracy_scores.std()),
        "cv_f1_mean": float(f1_scores.mean()),
        "cv_f1_std": float(f1_scores.std()),
        "cv_roc_auc_mean": float(roc_auc_scores.mean()),
        "cv_roc_auc_std": float(roc_auc_scores.std()),
        "cv_folds": n_folds,
    }


def archive_current_model(
    model_path: str = "models/xgboost_model.pkl",
    report_path: str = "models/evaluation_report.json",
    plots_dir: str = "models/plots",
) -> bool:
    """
    Archive the current production model before training a new one.

    This function:
    1. Checks if a model exists at the root level
    2. Detects the next version number (v3, v4, etc.)
    3. Prompts user to archive
    4. Moves current model to versions/v{N}_*/

    Returns:
        True if archived (or no model exists), False if user declined
    """
    import shutil
    from datetime import datetime

    model_path = Path(model_path)
    report_path = Path(report_path)
    plots_dir = Path(plots_dir)

    # Check if current model exists
    if not model_path.exists():
        print("\n  No existing model found - this is the first training")
        return True

    # Find next version number
    versions_dir = Path("models/versions")
    versions_dir.mkdir(parents=True, exist_ok=True)

    existing_versions = [d.name for d in versions_dir.iterdir() if d.is_dir() and d.name.startswith("v")]
    version_numbers = []
    for v in existing_versions:
        try:
            num = int(v.split("_")[0][1:])  # Extract number from "v2_..."
            version_numbers.append(num)
        except (ValueError, IndexError):
            pass

    next_version = max(version_numbers, default=0) + 1

    # Load current model's metrics to get sample count
    import pickle
    try:
        with open(model_path, "rb") as f:
            current_model_data = pickle.load(f)
            n_samples = current_model_data.get("metrics", {}).get("n_test_samples", 0) * 5  # Estimate total from test
    except:
        n_samples = 0

    # Prompt user
    print(f"\n{'='*60}")
    print(f"EXISTING MODEL DETECTED")
    print(f"{'='*60}")
    print(f"  Current model: {model_path}")
    print(f"  Next version:  v{next_version}")
    print(f"\nArchiving preserves the current model for:")
    print(f"  - Comparison with new training results")
    print(f"  - Rollback capability if new model underperforms")
    print(f"  - Jury presentation (showing iterative improvement)")

    response = input(f"\nArchive current model as v{next_version}? [Y/n]: ").strip().lower()

    if response in ["n", "no"]:
        print("  Skipping archive - current model will be OVERWRITTEN")
        return False

    # Create version directory
    version_name = f"v{next_version}_retrained_{n_samples}samples" if n_samples > 0 else f"v{next_version}_retrained"
    version_dir = versions_dir / version_name
    version_dir.mkdir(parents=True, exist_ok=True)

    # Archive model file
    if model_path.exists():
        shutil.copy(model_path, version_dir / "xgboost_model.pkl")
        print(f"  ✓ Archived: {model_path.name}")

    # Archive evaluation report
    if report_path.exists():
        shutil.copy(report_path, version_dir / "evaluation_report.json")
        print(f"  ✓ Archived: {report_path.name}")

    # Archive plots
    if plots_dir.exists() and plots_dir.is_dir():
        version_plots_dir = version_dir / "plots"
        version_plots_dir.mkdir(exist_ok=True)
        for plot_file in plots_dir.glob("*.png"):
            shutil.copy(plot_file, version_plots_dir / plot_file.name)
        print(f"  ✓ Archived: plots/ ({len(list(plots_dir.glob('*.png')))} files)")

    # Create notes file
    notes_path = version_dir / "notes.txt"
    with open(notes_path, "w") as f:
        f.write(f"# Version {next_version} - Archived Before Retraining\n\n")
        f.write(f"**Archived**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"**Reason**: New training session started\n\n")
        f.write("## Model Files\n\n")
        f.write("All production model files were archived to this directory:\n")
        f.write("- xgboost_model.pkl\n")
        f.write("- evaluation_report.json\n")
        f.write("- plots/\n\n")
        f.write("See evaluation_report.json for performance metrics.\n")

    print(f"  ✓ Created: notes.txt")
    print(f"\n  Archived to: {version_dir}")
    print(f"{'='*60}\n")

    return True


def save_model(
    model: xgb.XGBClassifier,
    feature_names: list[str],
    metrics: dict,
    model_path: str,
) -> None:
    """Save trained model and metadata."""
    import pickle

    path = Path(model_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "classifier": model,
        "regressor": None,  # Placeholder for future price prediction model
        "feature_names": feature_names,
        "metrics": metrics,
        "trained_at": pd.Timestamp.now().isoformat(),
    }

    with open(path, "wb") as f:
        pickle.dump(data, f)

    print(f"\nModel saved to {path}")
    print(f"  - Classifier: XGBClassifier ({model.n_estimators} estimators)")
    print(f"  - Features: {len(feature_names)} columns")


def save_evaluation_report(metrics: dict, cv_metrics: dict, output_path: str) -> None:
    """Save evaluation metrics as JSON report."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    report = {
        "model_type": "XGBoost Binary Classifier",
        "task": "Maker vs Taker Order Decision",
        "evaluation": metrics,
        "cross_validation": cv_metrics,
    }

    with open(path, "w") as f:
        json.dump(report, f, indent=2)

    print(f"Evaluation report saved to {path}")


def generate_plots(
    model: xgb.XGBClassifier,
    X_test: np.ndarray,
    y_test: np.ndarray,
    feature_names: list[str],
    output_dir: str,
) -> None:
    """Generate evaluation plots (confusion matrix, feature importance, ROC curve)."""
    try:
        import matplotlib
        matplotlib.use("Agg")  # Non-interactive backend
        import matplotlib.pyplot as plt
        from sklearn.metrics import RocCurveDisplay, ConfusionMatrixDisplay
    except ImportError:
        print("\nmatplotlib not installed, skipping plots.")
        print("Install with: pip install matplotlib")
        return

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    # 1. Confusion Matrix
    fig, ax = plt.subplots(figsize=(6, 5))
    ConfusionMatrixDisplay.from_estimator(
        model, X_test, y_test,
        display_labels=["Taker", "Maker"],
        cmap="Blues",
        ax=ax,
    )
    ax.set_title("Confusion Matrix - Maker/Taker Prediction")
    fig.tight_layout()
    fig.savefig(out / "confusion_matrix.png", dpi=150)
    plt.close(fig)
    print(f"  Saved confusion_matrix.png")

    # 2. Feature Importance (top 15)
    importance = model.feature_importances_
    pairs = sorted(zip(feature_names, importance), key=lambda x: x[1], reverse=True)
    top_n = min(15, len(pairs))
    names = [p[0] for p in pairs[:top_n]][::-1]
    values = [p[1] for p in pairs[:top_n]][::-1]

    fig, ax = plt.subplots(figsize=(8, 6))
    ax.barh(names, values, color="steelblue")
    ax.set_xlabel("Feature Importance (Gain)")
    ax.set_title("Top Features for Maker/Taker Decision")
    fig.tight_layout()
    fig.savefig(out / "feature_importance.png", dpi=150)
    plt.close(fig)
    print(f"  Saved feature_importance.png")

    # 3. ROC Curve
    fig, ax = plt.subplots(figsize=(6, 5))
    RocCurveDisplay.from_estimator(model, X_test, y_test, ax=ax)
    ax.plot([0, 1], [0, 1], "k--", label="Random (AUC=0.5)")
    ax.set_title("ROC Curve - Maker/Taker Classifier")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out / "roc_curve.png", dpi=150)
    plt.close(fig)
    print(f"  Saved roc_curve.png")

    print(f"\nAll plots saved to {out}/")


def main():
    parser = argparse.ArgumentParser(
        description="Train XGBoost maker/taker classifier"
    )
    parser.add_argument(
        "--data", type=str, default="data/training_data.csv",
        help="Path to training CSV (default: data/training_data.csv)"
    )
    parser.add_argument(
        "--model", type=str, default="models/xgboost_model.pkl",
        help="Path to save model (default: models/xgboost_model.pkl)"
    )
    parser.add_argument(
        "--report", type=str, default="models/evaluation_report.json",
        help="Path to save evaluation report (default: models/evaluation_report.json)"
    )
    parser.add_argument(
        "--plots-dir", type=str, default="models/plots",
        help="Directory for evaluation plots (default: models/plots)"
    )
    parser.add_argument(
        "--no-plots", action="store_true",
        help="Skip generating plots"
    )
    parser.add_argument(
        "--test-size", type=float, default=0.2,
        help="Test set proportion (default: 0.2)"
    )
    args = parser.parse_args()

    print("=" * 60)
    print("XGBOOST MODEL TRAINING - MAKER/TAKER PREDICTION")
    print("=" * 60)

    # Step 1: Load data
    print(f"\n--- Loading Data ---")
    X, y, feature_names = load_and_prepare_data(args.data)

    if len(X) < 50:
        print(f"\nWARNING: Only {len(X)} samples. Recommend at least 200 for reliable results.")
        print("Run collect_training_data.py for longer to get more data.")

    # Step 2: Train/test split
    print(f"\n--- Train/Test Split ---")
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=args.test_size, random_state=42, stratify=y
    )
    print(f"  Training set: {len(X_train)} samples")
    print(f"  Test set:     {len(X_test)} samples")

    # Step 3: Train model
    model = train_xgboost(X_train, y_train, X_test, y_test, feature_names)

    # Step 4: Evaluate
    metrics = evaluate_model(model, X_test, y_test, feature_names)

    # Step 5: Cross-validation
    cv_metrics = cross_validate(X, y)

    # Step 6: Archive current model (if it exists)
    archive_current_model(args.model, args.report, args.plots_dir)

    # Step 7: Save new model
    print(f"\n--- Saving Model ---")
    all_metrics = {**metrics, **cv_metrics}
    save_model(model, feature_names, all_metrics, args.model)

    # Step 8: Save report
    save_evaluation_report(metrics, cv_metrics, args.report)

    # Step 9: Generate plots
    if not args.no_plots:
        print(f"\n--- Generating Plots ---")
        generate_plots(model, X_test, y_test, feature_names, args.plots_dir)

    # Summary
    print(f"\n{'='*60}")
    print("TRAINING COMPLETE")
    print(f"{'='*60}")
    print(f"  Model:     {args.model}")
    print(f"  Accuracy:  {metrics['accuracy']*100:.1f}%")
    print(f"  ROC-AUC:   {metrics['roc_auc']:.3f}")
    print(f"  CV Acc:    {cv_metrics['cv_accuracy_mean']*100:.1f}% +/- {cv_metrics['cv_accuracy_std']*100:.1f}%")
    print(f"\nThe model is ready to use in the trading bot.")
    print(f"It will be loaded automatically from {args.model}")


if __name__ == "__main__":
    main()
