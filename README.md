# drowsiness_detection

## Runtime

Default field-trial startup uses the USB webcam through OpenCV and does not
start IMU/pothole telemetry:

```sh
python main.py
```

Runtime/device/server defaults live in `config/runtime_config.yaml`. Existing
environment variables still override that file, for example:

```sh
DS_IDENTITY_MODE=operation python main.py
DS_REMOTE_INCLUDE_IMAGE=0 python main.py
DS_IMU_ENABLED=1 DS_IMU_PUBLISH_ENABLED=1 python main.py
```

## Raspberry Pi Commands

From the project folder:

```sh
cd ~/Downloads/dd_2025
source venv/bin/activate
python main.py
```

Headless/service-style manual run:

```sh
DS_HEADLESS=1 python main.py
```

Force USB webcam index 0:

```sh
DS_CAMERA_SOURCE=opencv DS_CAMERA_INDEX=0 python main.py
```

Use a Raspberry Pi camera module instead of USB:

```sh
DS_CAMERA_SOURCE=picamera2 python main.py
```

Quick hardware checks:

```sh
python -m src.infrastructure.hardware.camera
python -m src.gps.standalone_test --port /dev/ttyAMA0 --baud 9600
python -m src.compass.standalone_test
python -m src.imu.standalone_test
```

Common systemd commands:

```sh
sudo systemctl daemon-reload
sudo systemctl start dd.service
sudo systemctl stop dd.service
sudo systemctl restart dd.service
sudo systemctl status dd.service
journalctl -u dd.service -f
sudo systemctl enable dd.service
sudo systemctl disable dd.service
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
