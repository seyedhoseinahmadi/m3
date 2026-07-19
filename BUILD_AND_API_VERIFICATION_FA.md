# بررسی Build و API نسخه 0.4.2

## متغیر GitHub

```text
HIMATE_DIRECTORY_API_URL=https://mangroup.ir
```

## فایل خروجی Release

```text
HiMateSync_Setup.exe
```

## API ثبت اثر انگشت

```http
POST https://mangroup.ir/api/fingerprints/registe
```

بدنه ارسالی دقیقاً چهار فیلد دارد:

```json
{
  "username": "ali.rezaei",
  "device_id": 1,
  "device_code": "HZ001",
  "finger_id": 8
}
```
