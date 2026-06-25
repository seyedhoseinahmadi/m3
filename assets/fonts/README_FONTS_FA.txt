فونت‌های واقعی داخل این پکیج قرار داده نشده‌اند.

برای فعال شدن فونت AFY در نسخه نهایی، فایل‌های مجاز/لایسنس‌دار را قبل از Build در همین پوشه بگذارید:

AFYRegular.ttf
AFYBold.ttf

اگر فقط WOFF/WOFF2 دارید، می‌توانید این‌ها را قرار دهید و Build خودش با prepare_fonts.py تلاش می‌کند به TTF تبدیل کند:

AFYRegular.woff یا AFYRegular.woff2
AFYBold.woff یا AFYBold.woff2

برنامه اگر TTFها وجود داشته باشند، در ویندوز آن‌ها را به‌صورت خصوصی Load می‌کند.
در غیر این صورت از Tahoma استفاده می‌شود.
