# Hotfix 0.3.5 - HTTP 422 Handling

## مشکل

Laravel برای دستگاه ثبت‌نشده این پاسخ را می‌داد:

```json
{
  "ok": false,
  "ack_allowed": false,
  "message": "Unknown or inactive device_code..."
}
```

اما همراه با HTTP 422.

برنامه ویندوز HTTP 422 را قبل از بررسی JSON به‌عنوان Exception حساب می‌کرد؛ بنابراین UI همچنان «خطا» نشان می‌داد.

## اصلاح

از این نسخه، اگر سرور JSON معتبر برگرداند، حتی با HTTP 422، برنامه آن را تحلیل می‌کند.

برای device_code نامعتبر/غیرفعال:

```text
وصل / دستگاه ثبت نشده
```

نمایش داده می‌شود.

## امنیت

ACK همچنان زده نمی‌شود، چون `ack_allowed:false` است.
رکورد روی دستگاه و SQLite باقی می‌ماند.
