# ساخت خودکار EXE/Setup با هر Commit مثل WooDesk

این نسخه دیگر از `upload-artifact` استفاده نمی‌کند، چون Artifact quota ممکن است سریع پر شود.

در این نسخه با هر commit/push روی شاخه `main` یا `master`، GitHub Actions خودش:

```text
1. Python را آماده می‌کند
2. پکیج‌ها را نصب می‌کند
3. SERVER_URL را داخل EXE می‌بندد
4. EXE را با PyInstaller می‌سازد
5. Setup.exe را با Inno Setup می‌سازد
6. فایل خروجی را داخل GitHub Releases آپدیت می‌کند
```

## خروجی نهایی

در بخش Releases فایل‌ها را می‌بینی:

```text
HozoorSyncCustomer_Setup_latest.exe
HozoorSyncCustomer_Setup_v0_2_5.exe
```

Release ثابت:

```text
hozoor-customer-latest
```

یعنی هر بار commit بزنی، همین Release آپدیت می‌شود و ده‌ها Artifact جدا ساخته نمی‌شود.

## تنظیمات لازم در GitHub

### 1. فعال کردن Write Permission برای Actions

مسیر:

```text
Repository → Settings → Actions → General → Workflow permissions
```

گزینه زیر را انتخاب کن:

```text
Read and write permissions
```

و ذخیره کن.

### 2. تنظیم Server URL

مسیر:

```text
Repository → Settings → Secrets and variables → Actions → Variables
```

یک Variable بساز:

```text
HOZOOR_SERVER_URL = https://hozoor.example.com
```

اختیاری:

```text
HOZOOR_SERVER_ID = HOZOOR_MAIN
```

### 3. تنظیم Token اختیاری

اگر خواستی Agent Token هم داخل build برود، در Secrets بساز:

```text
HOZOOR_AGENT_TOKEN = your-token
```

## روش استفاده روزمره

از این به بعد فقط:

```text
فایل‌ها را آپلود/ویرایش کن
Commit بزن
GitHub خودش Setup.exe می‌سازد
در Releases دانلود کن
```

نیازی نیست دستی Run بزنی، مگر اینکه بخواهی با server_url متفاوت تست کنی.

## چرا بهتر از Artifact است؟

- Artifact quota را پر نمی‌کند
- خروجی همیشه جای ثابت دارد
- برای محصول نهایی تمیزتر است
- مثل Workflow قبلی WooDesk می‌شود
- روزی چندین بار commit هم قابل تحمل‌تر است

## هشدار

فایل‌های Release هم بهتر است نسخه‌های زیاد نگه ندارند. این Workflow با `replacesArtifacts: true` فایل‌های قبلی همان Release را جایگزین می‌کند.
