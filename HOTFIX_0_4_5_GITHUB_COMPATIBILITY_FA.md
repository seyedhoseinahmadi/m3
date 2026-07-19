# اصلاح قطعی Build نسخه 0.4.5

خطای نسخه 0.4.5 به این علت بود که فایل جدید Installer روی Repository قرار گرفته بود، اما GitHub هنوز Workflow قدیمی را اجرا می‌کرد.

نشانه قطعی آن در Log این خط بود:

```text
Run New-Item -ItemType Directory -Force -Path Output
```

Workflow قدیمی فایل زیر را می‌ساخت:

```text
dist\HozoorSyncCustomer.exe
```

در حالی که Installer جدید فقط دنبال این فایل بود:

```text
Output\HiMateSync.exe
```

نسخه 0.4.5 با هر دو ساختار سازگار است و Installer می‌تواند هرکدام از ورودی‌های زیر را استفاده کند:

```text
Output\HiMateSync.exe
dist\HiMateSync.exe
dist\HozoorSyncCustomer.exe
```

نام داخلی برنامه پس از نصب همچنان `HiMateSync.exe` و برند رابط `HiMate` است.

فایل `.github/workflows/build-latest.yml` جدید نیز خروجی Release را با نام زیر منتشر می‌کند:

```text
HiMateSync_Setup.exe
```
