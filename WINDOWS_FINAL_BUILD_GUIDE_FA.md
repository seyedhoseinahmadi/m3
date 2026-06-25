# راهنمای فنی ساخت نسخه نهایی ویندوز

## مرحله ۱: تنظیم سرور

با اجرای فایل build، مقدار Server URL وارد می‌شود:

```text
https://hozoor.example.com
```

نکته: مسیر API را داخل Server URL ننویسید.

درست:

```text
https://hozoor.example.com
```

اشتباه:

```text
https://hozoor.example.com/api/hozoor/events/batch
```

## مرحله ۲: ساخت EXE

PyInstaller فایل زیر را می‌سازد:

```text
dist\HozoorSyncCustomer.exe
```

## مرحله ۳: ساخت Setup

Inno Setup فایل زیر را می‌سازد:

```text
Output\HozoorSyncCustomer_Setup_v0_2_5.exe
```

## نصب روی مشتری

فایل Setup را روی سیستم مشتری اجرا کن.

## اجرای خودکار

در نصب، گزینه اجرای خودکار هنگام روشن شدن ویندوز وجود دارد.

## مسیر نصب

```text
C:\Program Files\Avaye Farda\Hozoor Sync
```

## مسیر داده‌ها

```text
%APPDATA%\HozoorSyncCustomer
```
