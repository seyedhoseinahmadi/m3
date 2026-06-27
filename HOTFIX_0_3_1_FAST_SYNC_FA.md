# Hotfix 0.3.2 - Fast Auto Sync

## مشکل

در نسخه قبل، Auto Sync حس کندی داشت چون:

- خواندن دستگاه هر ۲۰ ثانیه بود.
- ارسال به سرور هر ۲۰ ثانیه بود.
- برخی درخواست‌های جانبی مثل restore-events می‌توانستند قبل از آماده بودن Laravel چند ثانیه Timeout بدهند.
- UI هر ۲ ثانیه تازه می‌شد، اما Sync واقعی سریع نبود.

## اصلاح

مقادیر جدید:

```text
read_interval_seconds = 3
sync_interval_seconds = 5
heartbeat_interval_seconds = 30
restore_interval_seconds = 300
command_interval_seconds = 10
serial_timeout_seconds = 2
```

## منطق جدید

- خواندن دستگاه و ارسال رکوردها اولویت اول دارند.
- Restore از سرور دیگر ابتدای کار مزاحم Sync نمی‌شود.
- Command و Restore فقط وقتی سرور reachable باشد اجرا می‌شوند.
- Timeout درخواست‌ها کوتاه‌تر شد.
- نصب‌های قبلی اگر هنوز مقادیر کند قدیمی داشته باشند، به‌صورت خودکار به مقدار جدید migrate می‌شوند.
