# How Machine Learning Metrics Work - Step by Step

This document explains exactly how the model evaluation metrics are calculated, so you can understand and reproduce them yourself.

---

## The Train/Test Split

**Step 1: Split the data**

```python
from sklearn.model_selection import train_test_split

# Load your CSV
df = pd.read_csv("data/training_combined.csv")

# Separate features (X) and labels (y)
X = df.drop("label", axis=1).values  # All columns except 'label'
y = df["label"].values                # Just the 'label' column

# Split: 80% training, 20% testing
X_train, X_test, y_train, y_test = train_test_split(
    X, y,
    test_size=0.2,      # 20% for testing
    random_state=42,    # For reproducibility
    stratify=y          # Keep same maker/taker ratio in both sets
)
```

**What this does:**
- Takes 2,457 samples
- Randomly selects 80% (1,965 samples) for training
- Keeps 20% (492 samples) for testing
- The model NEVER sees the test set during training

---

## Training the Model

**Step 2: Train XGBoost**

```python
import xgboost as xgb

model = xgb.XGBClassifier(
    max_depth=6,
    learning_rate=0.1,
    n_estimators=200,
    # ... other parameters
)

# Train ONLY on training set
model.fit(X_train, y_train)
```

**What happens:**
- XGBoost builds up to 200 decision trees
- Each tree learns from the 1,965 training samples
- The test set (492 samples) is completely hidden

---

## Making Predictions

**Step 3: Predict on test set**

```python
# Get predictions (0 or 1)
y_pred = model.predict(X_test)

# Get probabilities (0.0 to 1.0)
y_proba = model.predict_proba(X_test)[:, 1]
```

**Example output:**
```
Actual labels:  [1, 0, 1, 1, 0, ...]  (492 values)
Predictions:    [1, 1, 1, 0, 0, ...]  (492 values)
Probabilities:  [0.73, 0.45, 0.82, 0.31, ...]
```

---

## Calculating Metrics

### Confusion Matrix

**Step 4: Build confusion matrix**

```python
from sklearn.metrics import confusion_matrix

cm = confusion_matrix(y_test, y_pred)
```

**What it shows:**
```
                  Predicted
                Taker  Maker
Actual Taker  [  157    108  ]   ← 265 actual taker samples
Actual Maker  [   69    158  ]   ← 227 actual maker samples
```

**Read it like this:**
- Top-left (157): Predicted taker, was actually taker ✓ (True Negative)
- Top-right (108): Predicted maker, was actually taker ✗ (False Positive)
- Bottom-left (69): Predicted taker, was actually maker ✗ (False Negative)
- Bottom-right (158): Predicted maker, was actually maker ✓ (True Positive)

**Manual calculation:**
```
TN = 157  (correctly predicted taker)
FP = 108  (wrongly predicted maker)
FN = 69   (wrongly predicted taker)
TP = 158  (correctly predicted maker)

Total = 157 + 108 + 69 + 158 = 492 ✓
```

---

### Accuracy

**Formula:**
```
Accuracy = (Correct predictions) / (Total predictions)
         = (TP + TN) / (TP + TN + FP + FN)
```

**Calculation:**
```python
from sklearn.metrics import accuracy_score

accuracy = accuracy_score(y_test, y_pred)
# Or manually:
accuracy = (158 + 157) / 492 = 315 / 492 = 0.6402 = 64.0%
```

**Meaning:** The model got 64% of predictions correct.

---

### Precision

**Formula:**
```
Precision = (Correct maker predictions) / (All maker predictions)
          = TP / (TP + FP)
```

**Calculation:**
```python
from sklearn.metrics import precision_score

precision = precision_score(y_test, y_pred)
# Or manually:
precision = 158 / (158 + 108) = 158 / 266 = 0.594 = 59.4%
```

**Meaning:** When the model says "use maker", it's correct 59.4% of the time.

---

### Recall

**Formula:**
```
Recall = (Caught maker cases) / (All actual maker cases)
       = TP / (TP + FN)
```

**Calculation:**
```python
from sklearn.metrics import recall_score

recall = recall_score(y_test, y_pred)
# Or manually:
recall = 158 / (158 + 69) = 158 / 227 = 0.696 = 69.6%
```

**Meaning:** Of all actual maker opportunities, the model caught 69.6% of them.

---

### F1-Score

**Formula:**
```
F1 = 2 × (Precision × Recall) / (Precision + Recall)
```

**Calculation:**
```python
from sklearn.metrics import f1_score

f1 = f1_score(y_test, y_pred)
# Or manually:
f1 = 2 × (0.594 × 0.696) / (0.594 + 0.696)
   = 2 × 0.413 / 1.29
   = 0.641 = 64.1%
```

**Meaning:** Balanced measure that accounts for both precision and recall.

---

### ROC-AUC

**What is ROC-AUC?**

ROC (Receiver Operating Characteristic) curve plots:
- X-axis: False Positive Rate
- Y-axis: True Positive Rate (Recall)

AUC (Area Under Curve) measures the area under this curve.

**Calculation:**
```python
from sklearn.metrics import roc_auc_score

roc_auc = roc_auc_score(y_test, y_proba)  # Uses probabilities, not 0/1
```

**What it means:**
- 0.5 = Random guessing (coin flip)
- 0.689 = Our model (much better than random!)
- 1.0 = Perfect classifier

**Interpretation:**
"If I pick a random maker case and a random taker case, there's a 68.9% chance the model will rank the maker case higher (assign it a higher probability) than the taker case."

**Why it's important:**
- ROC-AUC is better than accuracy for imbalanced datasets
- It measures how well the model RANKS predictions
- A model can have 64% accuracy but very good ranking (ROC-AUC 0.689)

---

### Cross-Validation

**What is 5-Fold Cross-Validation?**

Instead of one train/test split, we do 5 different splits:

```
Fold 1: [Train Train Train Train | Test]
Fold 2: [Train Train Train Test  | Train]
Fold 3: [Train Train Test  Train | Train]
Fold 4: [Train Test  Train Train | Train]
Fold 5: [Test  Train Train Train | Train]
```

**Calculation:**
```python
from sklearn.model_selection import StratifiedKFold, cross_val_score

cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

# Train and test on each fold
accuracy_scores = cross_val_score(model, X, y, cv=cv, scoring="accuracy")
```

**Output:**
```
Fold 1: 67.7%
Fold 2: 60.6%
Fold 3: 56.8%
Fold 4: 62.3%
Fold 5: 66.4%

Mean: 62.8%
Std:  ±3.9%
```

**Why it's important:**
- Tests if the model works on different data splits
- Low standard deviation (3.9%) = stable/consistent model
- High standard deviation = model is overfitting to specific data

---

## Complete Example in Python

Here's a self-contained script you can run:

```python
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, confusion_matrix
)
import xgboost as xgb

# 1. Load data
df = pd.read_csv("data/training_combined.csv")
X = df.drop("label", axis=1).values
y = df["label"].values

print(f"Total samples: {len(df)}")
print(f"Features: {X.shape[1]}")
print(f"Maker: {(y==1).sum()} | Taker: {(y==0).sum()}")

# 2. Split data
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

print(f"\nTrain: {len(X_train)} | Test: {len(X_test)}")

# 3. Train model
model = xgb.XGBClassifier(
    max_depth=6,
    learning_rate=0.1,
    n_estimators=100,
    random_state=42
)

model.fit(X_train, y_train)

# 4. Predict
y_pred = model.predict(X_test)
y_proba = model.predict_proba(X_test)[:, 1]

# 5. Calculate metrics
accuracy = accuracy_score(y_test, y_pred)
precision = precision_score(y_test, y_pred)
recall = recall_score(y_test, y_pred)
f1 = f1_score(y_test, y_pred)
roc_auc = roc_auc_score(y_test, y_proba)
cm = confusion_matrix(y_test, y_pred)

# 6. Print results
print("\n=== METRICS ===")
print(f"Accuracy:  {accuracy:.4f} ({accuracy*100:.1f}%)")
print(f"Precision: {precision:.4f} ({precision*100:.1f}%)")
print(f"Recall:    {recall:.4f} ({recall*100:.1f}%)")
print(f"F1-Score:  {f1:.4f} ({f1*100:.1f}%)")
print(f"ROC-AUC:   {roc_auc:.4f}")

print("\n=== CONFUSION MATRIX ===")
print("                Predicted")
print("              Taker  Maker")
print(f"Actual Taker [ {cm[0][0]:4d}  {cm[0][1]:4d} ]")
print(f"Actual Maker [ {cm[1][0]:4d}  {cm[1][1]:4d} ]")

# Manual verification
TP = cm[1][1]
TN = cm[0][0]
FP = cm[0][1]
FN = cm[1][0]

print("\n=== MANUAL VERIFICATION ===")
print(f"Accuracy = (TP + TN) / Total")
print(f"         = ({TP} + {TN}) / {len(y_test)}")
print(f"         = {(TP + TN) / len(y_test):.4f} ✓")

print(f"\nPrecision = TP / (TP + FP)")
print(f"          = {TP} / ({TP} + {FP})")
print(f"          = {TP / (TP + FP):.4f} ✓")

print(f"\nRecall = TP / (TP + FN)")
print(f"       = {TP} / ({TP} + {FN})")
print(f"       = {TP / (TP + FN):.4f} ✓")
```

**Run it:**
```bash
python scripts/verify_metrics.py
```

---

## Where Metrics Are Calculated

In the actual training script (`scripts/train_model.py`):

| Metric | Function | Line |
|--------|----------|------|
| Accuracy | `accuracy_score(y_test, y_pred)` | ~185 |
| Precision | `precision_score(y_test, y_pred)` | Uses `classification_report()` |
| Recall | `recall_score(y_test, y_pred)` | Uses `classification_report()` |
| F1-Score | `f1_score(y_test, y_pred)` | Uses `classification_report()` |
| ROC-AUC | `roc_auc_score(y_test, y_proba)` | ~196 |
| Confusion Matrix | `confusion_matrix(y_test, y_pred)` | ~196 |
| Cross-Validation | `cross_val_score(model, X, y, cv=cv)` | ~220-227 |

---

## Key Takeaways

1. **Train/Test Split**: Model trains on 80%, tests on unseen 20%
2. **Accuracy**: Percentage of correct predictions (simple but can be misleading)
3. **Precision**: "Of predicted makers, how many were right?"
4. **Recall**: "Of actual makers, how many did we catch?"
5. **F1-Score**: Balanced metric combining precision and recall
6. **ROC-AUC**: Best overall metric - measures ranking quality (0.5=random, 1.0=perfect)
7. **Cross-Validation**: Tests stability across different data splits

**For the jury:**
"We used standard scikit-learn metrics on a held-out test set that the model never saw during training. ROC-AUC of 0.689 shows the model has learned real patterns, well above the random baseline of 0.5."
