# Hotfix 0.2.9

مشکل workflow قدیمی که دنبال فایل زیر می‌گشت اصلاح شد:

```text
Output\HozoorSyncCustomer_Setup_v0_2_5.exe
```

از این نسخه خروجی ثابت است:

```text
Output\HiMateSync_Setup.exe
```

و فقط یک workflow باید در ریپو باقی بماند:

```text
.github/workflows/build-latest.yml
```
