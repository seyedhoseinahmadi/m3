# فونت رابط کاربری HiMate

فایل‌های فونت مجاز را پیش از Build در همین پوشه قرار دهید:

- AFYRegular.woff2
- AFYBold.woff2

نسخه‌های WOFF نیز پشتیبانی می‌شوند:

- AFYRegular.woff
- AFYBold.woff

اسکریپت prepare_fonts.py قبل از Build آن‌ها را به این فایل‌های ویندوزی تبدیل می‌کند:

- AFYRegular.ttf
- AFYBold.ttf

نام واقعی Family داخل این فونت‌ها:
IRANYekanWeb

Build در صورت نبودن فونت‌ها متوقف می‌شود تا هیچ نسخه‌ای با Tahoma یا Segoe UI منتشر نشود.
فونت به‌صورت خصوصی از پوشه نصب برنامه Load می‌شود و لازم نیست روی ویندوز مشتری نصب باشد.
