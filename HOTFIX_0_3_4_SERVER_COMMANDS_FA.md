# Hotfix 0.3.7 - Server Commands / Fingerprint Enrollment

## هدف

هماهنگی Windows Agent با صف دستورهای Laravel برای اجرای دستورهای سروری روی دستگاه از طریق Serial/COM.

## تغییرات ویندوز

- پشتیبانی از `SET_TIME` با payload زیر:

```json
{"timestamp":"20260628043000"}
```

- سازگاری با نام قبلی `SET_SERVER_TIME` نیز حفظ شد.
- دستورهای اثر انگشت:

```text
ENROLL_FINGER  -> A {finger_id}
DELETE_FINGER  -> M {finger_id}
SET_TIME        -> TS {timestamp}
```

- زمان انتظار دستور تعریف اثر انگشت از 10 ثانیه به 90 ثانیه افزایش پیدا کرد.
- اگر دستگاه هیچ پاسخی ندهد، command به اشتباه success ثبت نمی‌شود.
- لاگ اجرای دستور و نتیجه در `hz_command_logs` و فایل لاگ ثبت می‌شود.

## تست سریع سمت Laravel

```bash
php artisan hozoor:queue-command HZ001 ENROLL_FINGER --finger=2 --employee=1
php artisan hozoor:queue-command HZ001 SET_TIME
```

بعد Windows Agent باید دستور را بگیرد، روی دستگاه اجرا کند و نتیجه را به `/api/hozoor/agent/command-result` برگرداند.
