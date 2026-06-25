# آمادگی اتصال Laravel برای نسخه ویندوز نهایی

این نسخه برای اتصال به Laravel آماده است.

Endpointهای مورد انتظار:

```text
POST /api/hozoor/events/batch
POST /api/hozoor/agent/heartbeat
POST /api/hozoor/agent/pull-commands
POST /api/hozoor/agent/command-result
POST /api/hozoor/agent/restore-events
POST /api/hozoor/agent/restore-confirm
```

نکته مهم برای ACK:

Laravel فقط وقتی اجازه ACK بدهد که رکوردها واقعاً ذخیره شده باشند.

پاسخ لازم:

```json
{
  "ok": true,
  "ack_allowed": true,
  "ack_until_event_id": 24
}
```

اگر `ack_allowed` وجود نداشته باشد یا false باشد، نرم‌افزار ویندوز ACK به دستگاه نمی‌زند.

Laravel باید device_code را اعتبارسنجی کند و نرم‌افزار را به device خاص وابسته نداند.
