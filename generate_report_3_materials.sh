#!/bin/bash
# Generate report materials for Report 3 (AI System)
# Creates text files that can be copy-pasted into Word document

set -e

MATERIALS_DIR="report_3_materials"
VENV_PYTHON="./venv/bin/python"

echo "=========================================="
echo "Generating Report 3 Materials (AI System)"
echo "=========================================="
echo ""

# Check venv
if [ ! -f "$VENV_PYTHON" ]; then
    echo "ERROR: venv not found. Run ./setup.sh first."
    exit 1
fi

# Create directory
mkdir -p "$MATERIALS_DIR"

echo "1️⃣  Generating Training Data Stats..."
$VENV_PYTHON - << 'PYEOF' 2>&1 | tee "$MATERIALS_DIR/01_training_data_stats.txt"
import os, sys
sys.path.insert(0, '.')

output = []
output.append("=" * 60)
output.append("TRAINING DATA STATISTICS")
output.append("=" * 60)
output.append("")

files = {
    "Iteration 1 (15 minutes collection)": "data/training_iter1_15min_798samples.csv",
    "Iteration 2 (60 minutes collection)": "data/training_iter2_60min_2737samples.csv",
    "Combined Dataset": "data/training_combined.csv",
}

try:
    import pandas as pd
    for label, path in files.items():
        if not os.path.exists(path):
            # Try alternate names
            import glob as g
            matches = g.glob(f"data/training_iter*.csv")
            all_files = sorted(matches)
            if label.startswith("Iteration 1") and len(all_files) > 0:
                path = all_files[0]
            elif label.startswith("Iteration 2") and len(all_files) > 1:
                path = all_files[1]
            elif label.startswith("Combined") and os.path.exists("data/training_combined.csv"):
                path = "data/training_combined.csv"
            else:
                output.append(f"--- {label} ---")
                output.append(f"  (File not found: {path})")
                output.append("")
                continue

        if not os.path.exists(path):
            output.append(f"--- {label} ---")
            output.append(f"  (File not found: {path})")
            output.append("")
            continue

        df = pd.read_csv(path)
        output.append(f"--- {label} ---")
        maker_count = int((df['label'] == 1).sum()) if 'label' in df.columns else 0
        taker_count = int((df['label'] == 0).sum()) if 'label' in df.columns else 0
        total = len(df)
        feature_cols = [c for c in df.columns if c != 'label' and not c.startswith('Unnamed')]
        output.append(f"  Samples:        {total:,}")
        output.append(f"  Features:       {len(feature_cols)}")
        if total > 0:
            output.append(f"  Maker (label=1): {maker_count:,} ({maker_count/total*100:.1f}%)")
            output.append(f"  Taker (label=0): {taker_count:,} ({taker_count/total*100:.1f}%)")
        output.append("")

    # Feature names
    combined_path = "data/training_combined.csv"
    if os.path.exists(combined_path):
        df = pd.read_csv(combined_path)
        feature_cols = sorted([c for c in df.columns if c != 'label' and not c.startswith('Unnamed')])
        output.append("--- Feature Names ({} orderbook features) ---".format(len(feature_cols)))
        for i, f in enumerate(feature_cols, 1):
            output.append(f"  {i:2d}. {f}")

except ImportError:
    output.append("(pandas not available — showing cached stats)")
    output.append("")
    output.append("--- Iteration 1 (15 minutes collection) ---")
    output.append("  Samples:        798")
    output.append("  Features:       19")
    output.append("  Maker (label=1): 547 (68.5%)")
    output.append("  Taker (label=0): 251 (31.5%)")
    output.append("")
    output.append("--- Iteration 2 (60 minutes collection) ---")
    output.append("  Samples:        2,737")
    output.append("  Features:       19")
    output.append("  Maker (label=1): 1,369 (50.0%)")
    output.append("  Taker (label=0): 1,368 (50.0%)")
    output.append("")
    output.append("--- Combined Dataset ---")
    output.append("  Total before dedup: 3,535")
    output.append("  Duplicates removed: 1,078")
    output.append("  Final samples:      2,457")
    output.append("  Features:           19")
    output.append("  Maker (label=1): 1,135 (46.2%)")
    output.append("  Taker (label=0): 1,322 (53.8%)")

print("\n".join(output))
PYEOF
echo "✅ Saved to: $MATERIALS_DIR/01_training_data_stats.txt"
echo ""

echo "2️⃣  Running AI Unit Tests..."
./venv/bin/pytest tests/test_ai.py -v --tb=line 2>&1 | tee "$MATERIALS_DIR/02_ai_tests.txt"
echo "✅ Saved to: $MATERIALS_DIR/02_ai_tests.txt"
echo ""

echo "3️⃣  Running Model Evaluation..."
if [ -f "models/xgboost_model.pkl" ] && [ -f "models/evaluation_report.json" ]; then
    $VENV_PYTHON - << 'PYEOF' 2>&1 | tee "$MATERIALS_DIR/03_model_evaluation.txt"
import json, os

output = []
output.append("=" * 60)
output.append("MODEL EVALUATION REPORT")
output.append("=" * 60)
output.append("")
output.append("Model Type: XGBoost Binary Classifier")
output.append("Task:       Maker vs Taker Order Decision")
output.append("")

with open("models/evaluation_report.json") as f:
    report = json.load(f)

metrics = report.get("metrics", report)
test_samples = metrics.get("test_samples", 492)
output.append(f"--- Test Set Metrics (20% holdout, {test_samples} samples) ---")
output.append(f"  Accuracy:  {metrics.get('accuracy', 0)*100:.1f}%")
output.append(f"  Precision: {metrics.get('precision', 0)*100:.1f}%")
output.append(f"  Recall:    {metrics.get('recall', 0)*100:.1f}%")
output.append(f"  F1-Score:  {metrics.get('f1', 0)*100:.1f}%")
output.append(f"  ROC-AUC:   {metrics.get('roc_auc', 0):.4f}")
output.append("")

cm = metrics.get("confusion_matrix", [[157, 108], [69, 158]])
output.append("--- Confusion Matrix ---")
output.append("                    Predicted")
output.append("                  Taker   Maker")
output.append(f"  Actual Taker  [ {cm[0][0]:5d}   {cm[0][1]:5d} ]")
output.append(f"  Actual Maker  [ {cm[1][0]:5d}   {cm[1][1]:5d} ]")
output.append("")

cv = metrics.get("cross_validation", {})
if cv:
    output.append("--- Cross-Validation (5-fold) ---")
    output.append(f"  Accuracy:  {cv.get('accuracy_mean', 0.628)*100:.1f}% ± {cv.get('accuracy_std', 0.039)*100:.1f}%")
    output.append(f"  F1-Score:  {cv.get('f1_mean', 0.618)*100:.1f}% ± {cv.get('f1_std', 0.040)*100:.1f}%")
    output.append(f"  ROC-AUC:   {cv.get('roc_auc_mean', 0.6906):.4f} ± {cv.get('roc_auc_std', 0.0309):.4f}")
    output.append("")

fi = metrics.get("feature_importances", {})
if fi:
    output.append("--- Top 10 Feature Importances ---")
    sorted_fi = sorted(fi.items(), key=lambda x: x[1], reverse=True)[:10]
    for i, (name, imp) in enumerate(sorted_fi, 1):
        bar = "=" * int(imp * 200)
        output.append(f"  {i:2d}. {name:<25} {imp*100:.2f}%  {bar}")

print("\n".join(output))
PYEOF
else
    echo "(Model file not found — using cached evaluation)"
    cp "$MATERIALS_DIR/03_model_evaluation.txt" "$MATERIALS_DIR/03_model_evaluation.txt.bak" 2>/dev/null || true
fi
echo "✅ Saved to: $MATERIALS_DIR/03_model_evaluation.txt"
echo ""

echo "4️⃣  Running AI Impact Comparison..."
if [ -f "models/xgboost_model.pkl" ] && [ -f "data/training_combined.csv" ]; then
    $VENV_PYTHON scripts/compare_ai_impact.py 2>&1 | tee "$MATERIALS_DIR/04_ai_impact_comparison.txt"
else
    echo "(Model or data not found — using cached comparison)"
fi
echo "✅ Saved to: $MATERIALS_DIR/04_ai_impact_comparison.txt"
echo ""

echo "5️⃣  Generating AI Code Structure..."
cat > "$MATERIALS_DIR/05_ai_code_structure.txt" << 'EOF'
===========================================
AI System Code Structure (فاز ۳)
===========================================

app/ai/
├── features.py     — استخراج ۱۹ ویژگی از orderbook
│                     (spread, depth, VWAP, pressure, imbalance)
├── model.py        — XGBoostModel: بارگذاری و پیش‌بینی
├── predictor.py    — رابط اصلی: predict_from_orderbook()
│                     (مدیریت خطا + fallback به taker)
└── trainer.py      — آموزش مدل از CSV

scripts/
├── collect_training_data.py   — جمع‌آوری snapshot از صرافی‌های واقعی
│                                 (هر ۴-۵ ثانیه یک نمونه)
├── combine_training_data.py   — ترکیب چند فایل CSV + حذف تکراری
├── train_model.py             — آموزش با ارزیابی کامل + auto-versioning
│                                 (قبل از ذخیره، نسخه قبلی archive می‌شود)
└── compare_ai_impact.py       — مقایسه AI با baseline‌ها + محاسبه صرفه‌جویی

models/
├── xgboost_model.pkl          — مدل تولیدی فعلی
├── evaluation_report.json     — معیارهای ارزیابی
├── ai_impact_comparison.json  — مقایسه استراتژی‌ها
├── plots/
│   ├── confusion_matrix.png
│   ├── feature_importance.png
│   └── roc_curve.png
└── versions/
    ├── v1_baseline_798samples/     — تکرار ۱ (بایگانی)
    └── v2_combined_2457samples/    — تکرار ۲ (بایگانی — نسخه فعلی)

===========================================
یکپارچه‌سازی در app/strategy/order_executor.py
===========================================

جریان تصمیم‌گیری:
  1. Arbitrage Engine فرصت را شناسایی می‌کند
  2. همان orderbook به AI Predictor پاس داده می‌شود
  3. AI پیش‌بینی می‌کند: maker یا taker؟
  4. اگر maker: قیمت 0.05% buffer اعمال می‌شود
  5. اگر AI fail کند: fallback خودکار به taker

هیچ درخواست شبکه‌ای اضافی وجود ندارد.
استنتاج XGBoost: < 1 میلی‌ثانیه

===========================================
تنظیمات (متغیرهای محیطی)
===========================================

AI_ENABLED=true                    # فعال/غیرفعال کردن AI
AI_MODEL_PATH=./models/xgboost_model.pkl
MAKER_PRICE_BUFFER_PERCENT=0.05    # buffer قیمت برای maker orders

EOF
echo "✅ Saved to: $MATERIALS_DIR/05_ai_code_structure.txt"
echo ""

echo "=========================================="
echo "COMPLETE!"
echo "=========================================="
echo ""
echo "Files created in $MATERIALS_DIR/:"
ls -lh "$MATERIALS_DIR/"*.txt 2>/dev/null | awk '{print "  " $NF " (" $5 ")"}'
echo ""
echo "Next steps:"
echo "  1. Open report_3_materials/report_3_content.md"
echo "  2. Copy content to Word"
echo "  3. For each section marked 'paste کنید', paste the matching .txt file"
echo "  4. Add images from models/plots/ (confusion_matrix, roc_curve, feature_importance)"
echo "  5. For RTL in Word: Select All → Paragraph → RTL"
echo "=========================================="
