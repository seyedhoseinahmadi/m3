# فونت AFY

فایل فونت داخل این پکیج قرار داده نشده است.

برای اینکه برنامه با فونت AFY ساخته شود، خودتان یکی از حالت‌های زیر را داخل همین پوشه در GitHub بگذارید:

```text
assets/fonts/AFYRegular.ttf
assets/fonts/AFYBold.ttf
```

یا اگر فقط WOFF/WOFF2 دارید:

```text
assets/fonts/AFYRegular.woff2
assets/fonts/AFYBold.woff2
```

در زمان Build، اسکریپت `prepare_fonts.py` تلاش می‌کند WOFF/WOFF2 را به TTF تبدیل کند.

اگر فونت موجود نباشد، برنامه از Segoe UI / Tahoma استفاده می‌کند.
