# HiMate Windows 0.4.8 — فونت داخلی قطعی

- Family واقعی فونت‌های AFY شناسایی شد: `IRANYekanWeb`.
- برنامه ابتدا همین Family را انتخاب می‌کند.
- WOFF/WOFF2 هنگام Build به TTF تبدیل می‌شود.
- Build در صورت نبودن Regular یا Bold متوقف می‌شود.
- Installer فایل‌های TTF را داخل `assets/fonts` برنامه نصب می‌کند.
- برنامه با `AddFontResourceExW(..., FR_PRIVATE, ...)` فونت را خصوصی Load می‌کند.
- نیازی به نصب فونت در Windows مشتری نیست.
