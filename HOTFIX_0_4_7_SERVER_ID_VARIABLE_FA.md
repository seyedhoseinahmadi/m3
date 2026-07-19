# اصلاح نسخه 0.4.7 — شناسه سرور فقط از Variable

- `SERVER_ID` دیگر هیچ مقدار پیش‌فرض یا هاردکد ندارد.
- در GitHub Actions مقدار فقط از Repository Variable با نام `HOZOOR_SERVER_ID` خوانده می‌شود.
- اگر Variable خالی باشد، Build با خطای واضح متوقف می‌شود و فایل اشتباه برای مشتری ساخته نمی‌شود.
- مقدار Variable هنگام Build داخل EXE همان مشتری تزریق می‌شود؛ برای مشتری بعدی فقط Variable را تغییر بده و دوباره Build بگیر.
- Payload رویدادها مقدار `server_id` را از همین Build Config می‌خواند.
