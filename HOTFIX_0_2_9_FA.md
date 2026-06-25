# Hotfix 0.2.9

## مشکل رفع‌شده

در نسخه قبلی، هنگام اجرای فایل نصب‌شده این خطا رخ می‌داد:

```text
NameError: name 'sys' is not defined
```

دلیل:
تابع `resource_path` برای تشخیص مسیر فایل‌های داخل PyInstaller از `sys._MEIPASS` استفاده می‌کرد، اما `import sys` در فایل اصلی نبود.

## اصلاح

به فایل زیر اضافه شد:

```text
hozoor_customer_app.py
```

خط اصلاحی:

```python
import sys
```

## نکته

پوشه `.github` لازم نیست دوباره تغییر کند، مگر اینکه هنوز workflow قدیمی داخل ریپو مانده باشد.
خروجی همچنان ثابت است:

```text
HozoorSyncCustomer_Setup.exe
```
