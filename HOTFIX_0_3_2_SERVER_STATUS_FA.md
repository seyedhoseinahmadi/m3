# Hotfix 0.3.8 - Server Status Fix

## مشکل

وقتی Laravel با HTTP 200 پاسخ می‌داد ولی `ok:false` برمی‌گرداند، نرم‌افزار ویندوز آن را به‌عنوان «خطای سرور» نشان می‌داد.

مثال:

```json
{
  "ok": false,
  "ack_allowed": false,
  "message": "Unknown or inactive device_code..."
}
```

در این حالت سرور قطع نیست؛ سرور وصل است ولی دستگاه در پنل Laravel ثبت یا فعال نشده است.

## اصلاح

از این نسخه، در UI این‌طور دیده می‌شود:

```text
وصل / دستگاه ثبت نشده
```

و همچنان ACK زده نمی‌شود.

## قانون

- خطای شبکه/SSL/Timeout = قطع یا خطا
- HTTP 200 + ok:false + device_code = وصل / دستگاه ثبت نشده
- ok:true + ack_allowed:true = ارسال موفق + ACK مجاز
