# ثبت اثر انگشت مستقیم با username

فهرست‌ها:

```text
GET https://mangroup.ir/api/users
GET https://mangroup.ir/api/branches
GET https://mangroup.ir/api/devices
```

ثبت پس از موفقیت سنسور:

```text
POST https://mangroup.ir/api/fingerprints/registe
```

بدنه دقیق ارسالی Windows:

```json
{
  "username": "ali.rezaei",
  "device_id": 1,
  "device_code": "HZ001",
  "finger_id": 8
}
```

Windows هیچ `user_id` در API ثبت اثر انگشت ارسال نمی‌کند.
قانون یکتا در Laravel: `UNIQUE(device_id, finger_id)`.
