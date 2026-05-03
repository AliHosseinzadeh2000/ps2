===========================================
Report 3 - AI System Materials
===========================================

این پوشه حاوی تمام مواد مورد نیاز برای گزارش شماره ۳ است.

Files:
------
report_3_content.md           - متن کامل گزارش به فارسی (اینجا شروع کنید)
01_training_data_stats.txt    - آمار داده‌های آموزشی (paste در بخش ۴)
02_ai_tests.txt               - نتایج تست‌های AI (paste در بخش ۸)
03_model_evaluation.txt       - نتایج ارزیابی مدل (paste در بخش ۵)
04_ai_impact_comparison.txt   - مقایسه استراتژی‌ها (paste در بخش ۶)
05_ai_code_structure.txt      - ساختار کد AI (paste در بخش ۳)

How to use:
-----------
1. فایل report_3_content.md را باز کنید
2. محتوا را در Word کپی کنید
3. در هر بخش که نوشته شده "paste کنید"، خروجی فایل txt مربوطه را paste کنید
4. تصاویر را از models/plots/ اضافه کنید:
   - confusion_matrix.png   (بخش ۵)
   - feature_importance.png (بخش ۵)
   - roc_curve.png          (بخش ۵)

Regenerate files:
-----------------
برای تولید مجدد فایل‌های txt با داده‌های به‌روز:
  ./generate_report_3_materials.sh

Notes:
------
- گزارش در مجموع ~۸-۱۰ صفحه خواهد شد
- اعداد دقیق از اجرای واقعی اسکریپت‌ها هستند
- برای راست‌به‌چپ کردن متن در Word: Select All → Paragraph → RTL
