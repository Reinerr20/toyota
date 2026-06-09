# drowsiness_detection

## Runtime

Default field-trial startup:

```sh
python main.py
```

Runtime/device/server defaults live in `config/runtime_config.yaml`. Existing
environment variables still override that file, for example:

```sh
DS_IDENTITY_MODE=operation python main.py
DS_REMOTE_INCLUDE_IMAGE=0 python main.py
DS_IMU_ENABLED=0 python main.py
```

## Evidence Check

Use this SQLite query to verify local image evidence and remote sync state:

```sh
sqlite3 data/cc.db "
SELECT
id,
time,
status,
user_id,
LENGTH(img_drowsiness) AS img_bytes,
remote_sent,
remote_attempts,
remote_last_error,
evidence_sent,
evidence_attempts,
evidence_last_error
FROM events
ORDER BY id DESC
LIMIT 20;
"
```

`img_bytes > 0` means local evidence capture is working. `remote_sent = 1`
means event metadata reached the backend. `evidence_sent = 1` means remote
image evidence reached the backend.
