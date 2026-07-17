# Hotfix 0.3.7 - API Timeout Fix

## مشکل

در بعضی درخواست‌ها، مخصوصاً روی هاست یا SSL کند، ویندوز فقط ۴ ثانیه منتظر پاسخ Laravel می‌ماند و خطای زیر دیده می‌شد:

```text
HTTPSConnectionPool(...): Read timed out. (read timeout=4)
```

## اصلاح

تایم‌اوت APIها افزایش یافت:

- heartbeat: 12 ثانیه
- events/batch: 20 ثانیه
- restore endpoints: 20 ثانیه
- pull-commands: 15 ثانیه
- command-result: 20 ثانیه
- تایم‌اوت پیش‌فرض API: 15 ثانیه

همچنین اگر خطا از نوع Read Timeout باشد، وضعیت سرور به جای خطای نامفهوم، به شکل زیر نمایش داده می‌شود:

```text
کند / تایم‌اوت
```

## نکته

این پچ سمت ویندوز است. اگر سرور بیش از ۱۵ تا ۲۰ ثانیه برای endpointهای ساده زمان می‌برد، سمت Laravel/هاست هم باید بررسی شود.
