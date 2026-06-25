# نسخه Stable GitHub

این نسخه طوری تنظیم شده که پوشه `.github` از این به بعد ثابت بماند.

## فایل ثابت

```text
.github/workflows/build-latest.yml
```

این فایل را دیگر در آپدیت‌های معمولی تغییر نده.

## خروجی ثابت

```text
HozoorSyncCustomer_Setup.exe
```

داخل Release ثابت:

```text
hozoor-customer-latest
```

## آپدیت‌های بعدی

در آپدیت‌های بعدی معمولاً فقط این‌ها را جایگزین کن:

```text
hozoor_customer_app.py
make_build_config.py
installer/HozoorSyncCustomer.iss
requirements.txt
READMEها
VERSION.txt
assets/ اگر فایل تصویری یا مجاز داشتی
```

## اگر از GitHub Upload استفاده می‌کنی

لازم نیست `.github` را هر بار آپلود کنی.  
فقط مراقب باش workflow قدیمی اضافه نشود.

## اگر نسخه جدید دادی

فقط `VERSION.txt` را تغییر بده.  
نام خروجی همچنان ثابت می‌ماند:

```text
HozoorSyncCustomer_Setup.exe
```
