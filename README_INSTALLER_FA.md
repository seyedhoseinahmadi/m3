# Hozoor Sync - نسخه نهایی Installer مشتری

نسخه:

```text
CUSTOMER-FINAL-INSTALLER-0.2.7
```

این پکیج برای ساخت فایل نصب نهایی ویندوز است:

```text
HozoorSyncCustomer_Setup.exe
```

## تفاوت با نسخه Portable

این نسخه Portable نیست.  
خروجی نهایی یک Setup واقعی برای نصب روی سیستم مشتری است.

بعد از نصب:

```text
C:\Program Files\Avaye Farda\Hozoor Sync\HozoorSyncCustomer.exe
```

داده‌ها، دیتابیس و لاگ‌ها در AppData ذخیره می‌شوند:

```text
%APPDATA%\HozoorSyncCustomer
```

## ساخت فایل نصب روی ویندوز

نیازها:

```text
Python 3.10+
Inno Setup 6
Internet برای نصب پکیج‌های Python
```

فایل زیر را اجرا کن:

```text
01_BUILD_SETUP_CUSTOMER.bat
```

در زمان ساخت از تو می‌پرسد:

```text
Server URL
Server ID
Agent Token اختیاری
```

این اطلاعات داخل EXE بسته می‌شود و مشتری نمی‌تواند Server URL را از UI تغییر دهد.

## خروجی

```text
Output\HozoorSyncCustomer_Setup.exe
```

## ساخت با GitHub

Repository را آپلود کن و از تب Actions اجرا کن:

```text
Build Hozoor Customer Setup
```

خروجی Artifact همان فایل نصب است.

## منطق امنیتی

- نرم‌افزار به device خاص قفل نیست.
- device_code از خود دستگاه خوانده می‌شود.
- نرم‌افزار فقط به سرور محصول متصل است.
- Laravel با device_code تصمیم می‌گیرد داده متعلق به کدام مشتری/شعبه است.
- ACK فقط با تایید سخت‌گیرانه Laravel زده می‌شود.


## ساخت خودکار مثل WooDesk

برای ساخت خودکار با هر Commit، فایل زیر را ببین:

```text
GITHUB_AUTO_BUILD_RELEASE_FA.md
```

این نسخه خروجی را داخل GitHub Releases می‌گذارد، نه Artifacts.
