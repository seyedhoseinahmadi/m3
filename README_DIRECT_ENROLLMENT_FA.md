# HiMate Windows 0.4.2 — ثبت مستقیم اثر انگشت

## جریان اصلی

1. ویندوز فهرست شعبه‌ها، افراد و دستگاه‌ها را از API می‌گیرد.
2. اپراتور فرد و دستگاه را انتخاب می‌کند.
3. ویندوز مستقیم به دستگاه متصل دستور `A {finger_id}` می‌فرستد.
4. فقط بعد از پاسخ موفق سنسور، نتیجه با `user_id` به Laravel ارسال می‌شود.
5. اگر Laravel موقتاً در دسترس نباشد، ثبت موفق در SQLite نگه‌داری و خودکار دوباره ارسال می‌شود.

## APIها

- `GET /api/users`
- `GET /api/branches`
- `GET /api/devices`
- `GET /api/fingerprints?device_id=...`
- `GET /api/fingerprints/next-id?device_id=...`
- `POST /api/fingerprints/register`
- سازگاری با مسیر قدیمی: `POST /api/fingerprints/registe`

## Payload نهایی ثبت

```json
{
  "registration_uuid": "uuid",
  "user_id": 34,
  "device_id": 1,
  "device_code": "HZ001",
  "finger_id": 8,
  "branch_id": 1,
  "registered_at": "2026-07-20 12:00:00"
}
```

`username` ارسال نمی‌شود. کلید یکتای سمت سرور:

```sql
UNIQUE(device_id, finger_id)
```

## GitHub Variables / Secrets

Variables:

```text
HOZOOR_SERVER_URL
HOZOOR_SERVER_ID
HIMATE_DIRECTORY_API_URL=https://mangroup.ir
```

Secrets:

```text
HOZOOR_AGENT_TOKEN
HIMATE_DIRECTORY_API_TOKEN
```
