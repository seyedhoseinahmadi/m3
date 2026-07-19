# HiMate Windows 0.4.6

- انتخاب شعبه از تب ثبت اثر انگشت حذف شد.
- انتخاب شعبه و دستگاه به تب تنظیمات منتقل شد.
- هنگام ذخیره، درخواست `POST /api/hozoor/agent/device-branch` فقط شامل `device_id` و `branch_id` است.
- تب ثبت اثر انگشت از دستگاه ذخیره‌شده در تنظیمات استفاده می‌کند.
- رویدادهای تردد به `POST /api/hozoor/events/batch` با قرارداد دقیق زیر ارسال می‌شوند:
  - `server_id`
  - `pc_name`
  - `agent_version`
  - `events[].device_code`
  - `events[].event_id`
  - `events[].finger_id`
  - `events[].event_time`
  - `events[].time_valid`
- فیلدهای داخلی `raw_line`، `source` و `record_hash` دیگر در Payload رویداد ارسال نمی‌شوند.
- انتخاب منبع EXE در Inno Setup با شرط واقعی وجود فایل اصلاح شد.
