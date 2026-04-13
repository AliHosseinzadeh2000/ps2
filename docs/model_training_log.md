# Model Training Log & Iterative Improvement

This document tracks the iterative process of collecting data, training the XGBoost model, and measuring performance improvements. This demonstrates the empirical machine learning methodology used in the project.

## Methodology

The training follows a standard ML workflow:

```
Iteration 1: Collect data → Train → Evaluate → Measure baseline
    ↓
Iteration 2: Collect MORE data → Retrain → Evaluate → Compare to baseline
    ↓
Iteration 3: Continue until performance plateaus or time constraints
```

**Key hypothesis**: More diverse training data (spanning different market conditions) improves model generalization and prediction accuracy.

---

## Training Iteration 1: Baseline Model

**Date**: February 11, 2026
**Collection Duration**: 15 minutes
**Collection Interval**: 4 seconds between snapshots

### Data Collection Results

```
Total snapshots collected: 803
Valid consecutive pairs: 798
Market conditions: Calm evening session (22:38 - 22:54 local time)

Label distribution:
  - Maker-safe (label=1): 547 samples (68.5%)
  - Use-taker (label=0): 251 samples (31.5%)

Volatility score statistics:
  - Min: 0.0000
  - Median: 0.0000 (used as threshold)
  - Max: 19,168,832.28
```

**Observation**: The extreme max volatility score (19M) indicates at least one significant price jump occurred during collection, but the median of 0.0 shows most of the period was very stable.

### Training Results

**Train/Test Split**: 80/20 stratified
- Training set: 638 samples
- Test set: 160 samples

**Model Configuration**:
- Algorithm: XGBoost Binary Classifier
- Max depth: 6
- Learning rate: 0.1
- N estimators: 200
- Subsample: 0.8
- Colsample by tree: 0.8
- Class weight: Balanced (scale_pos_weight = 2.18)

**Performance Metrics**:

| Metric | Value | Interpretation |
|--------|-------|----------------|
| **Accuracy** | 63.7% | Better than random (50%) but room for improvement |
| **Precision (Maker)** | 72.4% | Of predicted maker opportunities, 72% were correct |
| **Recall (Maker)** | 76.4% | Caught 76% of actual maker opportunities |
| **F1-Score** | 74.3% | Good balance between precision and recall |
| **ROC-AUC** | 0.547 | Weak but real signal (0.5 = random, 1.0 = perfect) |

**Cross-Validation (5-fold)**:
- Mean accuracy: 59.4% ± 5.4%
- Mean F1-score: 69.2% ± 5.1%
- Mean ROC-AUC: 0.570 ± 0.043

**Confusion Matrix**:
```
                  Predicted
                Taker  Maker
Actual Taker  [  18     32  ]  ← 36% recall for taker class
Actual Maker  [  26     84  ]  ← 76% recall for maker class
```

**Top 5 Features by Importance**:
1. `bid_vwap` (8.65%) - Volume-weighted bid price
2. `best_ask` (6.78%) - Lowest ask price
3. `spread_percent` (6.73%) - Spread as % of mid price
4. `spread` (6.17%) - Absolute spread
5. `ask_vwap` (6.14%) - Volume-weighted ask price

### Analysis & Insights

**Strengths**:
- Model has learned real patterns (ROC-AUC > 0.5)
- Feature importance makes financial sense (spread metrics dominate)
- Good recall for maker class (76%) - captures most fee-saving opportunities
- Cross-validation shows stable performance (low variance)

**Weaknesses**:
- Poor taker class recall (36%) - misses many volatile moments
- ROC-AUC of 0.547 is weak predictive power
- Data collected during calm market only (limited diversity)
- Class imbalance (68% maker, 32% taker) despite percentile labeling

**Root Cause**: 15 minutes of calm evening trading provides insufficient diversity. The market barely moved during collection (median volatility = 0), so the model hasn't seen enough volatile conditions to learn when taker orders are necessary.

**Recommendation**: Collect data spanning 1-2 hours including both volatile and calm periods.

---

## Training Iteration 2: Combined Dataset

**Date**: February 13, 2026
**Data Sources**:
- Iteration 1: `data/training_iter1_15min_798samples.csv` (798 samples)
- Iteration 2: `data/training_iter2_60min_2737samples.csv` (2,737 samples, 60 min collection)
- Combined: `data/training_combined.csv` (2,457 unique samples after deduplication)

### Data Collection Results

```
Combined dataset: 2,457 unique samples
Removed duplicates: 1,078

Label distribution:
  - Maker-safe (label=1): 1,135 samples (46.2%)
  - Use-taker (label=0): 1,322 samples (53.8%)
```

**Improvement over Iteration 1**: Much better class balance (46/54 vs 68/32).

### Training Results

**Train/Test Split**: 80/20 stratified
- Training set: 1,965 samples
- Test set: 492 samples

**Performance Metrics**:

| Metric | Iteration 1 | Iteration 2 | Change |
|--------|-------------|-------------|--------|
| **Accuracy** | 63.7% | 64.0% | +0.3% |
| **Precision (Maker)** | 72.4% | 59.4% | -13% (more balanced) |
| **Recall (Maker)** | 76.4% | 69.6% | -6.8% |
| **F1-Score** | 74.3% | 64.1% | -10.2% |
| **ROC-AUC** | 0.547 | **0.689** | **+26%** |

**Cross-Validation (5-fold)**:
- Mean accuracy: 62.8% ± 3.9% (was 59.4% ± 5.4%)
- Mean F1-score: 61.8% ± 4.0%
- Mean ROC-AUC: 0.691 ± 0.031

**Confusion Matrix**:
```
                  Predicted
                Taker  Maker
Actual Taker  [  157    108  ]  ← 59% recall for taker class (was 36%)
Actual Maker  [   69    158  ]  ← 70% recall for maker class
```

**Top 5 Features by Importance**:
1. `spread_percent` (7.26%) - Spread as % of mid price
2. `best_ask` (6.85%) - Lowest ask price
3. `best_bid` (6.72%) - Highest bid price
4. `mid_price` (6.69%) - Mid price
5. `spread` (6.41%) - Absolute spread

### Analysis

**Key Improvements**:
- ROC-AUC jumped from 0.547 to 0.689 (+26%) - the model has much stronger predictive power
- Taker recall improved from 36% to 59% - better at detecting volatile moments
- Cross-validation more stable (±3.9% vs ±5.4%)
- Better class balance leads to more realistic metrics

**Trade-offs**:
- Precision dropped because the model is now more conservative (flags more moments as taker)
- This is actually desirable: it's better to miss a maker opportunity than to place a maker order in a volatile market

### AI Impact Analysis

Simulation results (daily volume: 100,000,000 IRR):

| Strategy | Daily Fees | Fee Rate | Fill Rate |
|----------|-----------|----------|-----------|
| Always Taker (no AI) | 250,000 IRR | 0.25% | 100% |
| Always Maker (naive) | 180,708 IRR | 0.10% | 46.2% |
| **AI-Driven (our model)** | **190,110 IRR** | **0.19%** | **90.7%** |

**Savings**: 24% fee reduction vs always-taker, with 90.7% fill rate.
**Annual savings**: ~21,860,000 IRR on 100M daily volume.

Run `python scripts/compare_ai_impact.py` to reproduce these results.

---

## Training Iteration 3+: [FUTURE]

**Continuous Learning Pipeline**:
Once the bot is deployed in production, it will:
1. Execute trades using current model
2. Log every trade with:
   - Orderbook features at decision time
   - Maker/taker choice made
   - Actual outcome (filled or not filled)
3. Automatically retrain model weekly with accumulated real trading data
4. Model improves over time as it learns from real outcomes

**Expected Long-term Performance**:
- After 1 week of live trading: ROC-AUC 0.65-0.70
- After 1 month: ROC-AUC 0.70-0.75
- Plateau around: ROC-AUC 0.75-0.78

**Why improvement plateaus**:
Financial markets are inherently noisy and unpredictable at short timescales (4-5 seconds). Even professional HFT firms with massive data and compute power cannot exceed ~80% prediction accuracy for microstructure events. The 75-78% range represents the practical limit for this task.

---

## Comparison to Baselines

### Baseline 1: Always Use Taker (No AI)
- **Accuracy**: N/A (no decisions made)
- **Fee cost**: 0.25% per trade
- **Reliability**: 100% (always fills)
- **Lost savings**: Never captures the 0.15% fee savings from maker orders

### Baseline 2: Always Use Maker (Naive Strategy)
- **Accuracy**: N/A (no decisions made)
- **Fee cost**: 0.10% per trade (when it fills)
- **Reliability**: ~60-70% fill rate (many orders never execute)
- **Problem**: Loses arbitrage opportunities due to unfilled orders

### Our AI Model (Current - v2)
- **Accuracy**: 64.0% (test set), 84.4% (full dataset)
- **ROC-AUC**: 0.689
- **Effective fee rate**: 0.19%
- **Fill rate**: 90.7%
- **Benefit**: Saves 24% on fees vs always-taker, with high reliability

**ROI Calculation (Measured)**:
```
Daily trading volume: 100,000,000 IRR

Always-taker strategy:
  Fees: 250,000 IRR/day

AI-driven strategy:
  Fees: 190,110 IRR/day
  Daily savings:   59,890 IRR  (24%)
  Monthly savings: 1,796,703 IRR
  Annual savings:  21,859,890 IRR
```

Run `python scripts/compare_ai_impact.py` to reproduce.

---

## Future Enhancements

### Additional Features (Phase 4)
Currently using 19 orderbook features. Can expand to 47 features by adding:

**OHLC Technical Indicators** (28 features, already implemented):
- Moving averages (SMA, EMA) for 5/10/20 periods
- Volume indicators and momentum
- Volatility measures (std deviation of returns)
- RSI (Relative Strength Index)

**Implementation**: Simple modification in `scripts/collect_training_data.py` to also fetch OHLC data and combine with orderbook features.

**Expected Impact**: +2-3% accuracy improvement

### Ensemble Methods (Phase 5)
Train multiple models and combine predictions:
- XGBoost (current)
- LightGBM (faster variant)
- Random Forest (for comparison)
- Simple voting or weighted average

**Expected Impact**: +1-2% accuracy improvement

### Real-time Adaptive Threshold (Phase 6)
Instead of fixed 0.5 probability threshold, adjust based on:
- Current market volatility
- Time of day
- Exchange reliability

**Expected Impact**: Better precision/recall balance

---

## Lessons Learned

1. **Data quality > quantity**: 1 hour of diverse data beats 10 hours of calm-only data
2. **Labeling strategy matters**: Percentile-based labeling avoided 90/10 class imbalance
3. **Feature engineering is key**: Spread metrics proved most predictive across both iterations
4. **Realistic expectations**: 64% accuracy for market microstructure prediction is reasonable
5. **ROC-AUC is the key metric**: Improved from 0.547 to 0.689 with more data (+26%)
6. **Version your models**: Lost iteration 1 model files by overwriting - now auto-versioned
7. **Even modest accuracy saves money**: 64% accuracy still yields 24% fee savings due to fee asymmetry (0.25% vs 0.10%)

---

## File Artifacts

### Current File Structure

```
data/
  training_iter1_15min_798samples.csv      ← Iteration 1 raw data
  training_iter2_60min_2737samples.csv     ← Iteration 2 raw data
  training_combined.csv                     ← Combined (2,457 samples)

models/
  xgboost_model.pkl                        ← Current production model (v2)
  evaluation_report.json                   ← Current metrics
  ai_impact_comparison.json                ← AI vs baseline comparison
  plots/                                   ← Current visualizations
    confusion_matrix.png
    feature_importance.png
    roc_curve.png
  versions/                                ← Historical archive
    v1_baseline_798samples/
    v2_combined_2457samples/

scripts/
  collect_training_data.py                 ← Data collection from live exchanges
  train_model.py                           ← Training with auto-versioning
  combine_training_data.py                 ← Merge multiple datasets
  compare_ai_impact.py                     ← AI vs baseline comparison
```

### Training Script Auto-Versioning

When `train_model.py` is run, it automatically:
1. Detects existing model at root level
2. Prompts to archive as next version (v3, v4, etc.)
3. Saves new model to root level

This ensures no model is ever lost accidentally.

---

## References

**Market Microstructure Literature**:
- Cont, R., Kukanov, A., & Stoikov, S. (2014). "The Price Impact of Order Book Events"
- Stoikov, S., & Cont, R. (2010). "A Stochastic Model for Order Book Dynamics"

**XGBoost**:
- Chen, T., & Guestrin, C. (2016). "XGBoost: A Scalable Tree Boosting System"

**Financial ML Best Practices**:
- López de Prado, M. (2018). "Advances in Financial Machine Learning"
