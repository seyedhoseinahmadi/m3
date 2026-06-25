# قانون جدید Build

از این نسخه به بعد پوشه `.github` نباید در هر آپدیت تغییر کند.

## چیزی که ثابت می‌ماند

```text
.github/workflows/build-latest.yml
```

این فایل همیشه یک خروجی ثابت می‌سازد:

```text
HozoorSyncCustomer_Setup.exe
```

و آن را داخل Release ثابت زیر می‌گذارد:

```text
hozoor-customer-latest
```

## چیزی که در آپدیت‌های بعدی تغییر می‌کند

معمولاً فقط این فایل‌ها:

```text
hozoor_customer_app.py
make_build_config.py
installer/HozoorSyncCustomer.iss
READMEها
VERSION.txt
```

## روش آپدیت روزمره

```text
1. فایل‌های جدید را روی قبلی‌ها بریز
2. اگر .github قبلاً درست است، دیگر لازم نیست آن را تغییر بدهی
3. Commit بزن
4. GitHub خودش Setup.exe جدید را داخل Releases جایگزین می‌کند
```

## خروجی ثابت

همیشه از Releases این فایل را دانلود کن:

```text
HozoorSyncCustomer_Setup.exe
```
