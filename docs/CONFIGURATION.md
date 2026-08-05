# Configuration

## Resolution order and notation

Runtime values resolve in this order: environment override, `config/runtime_config.yaml`, then the fallback in `src/app/orchestrator.py`. `main.py` additionally defaults `DS_CAMERA_SOURCE` to `opencv`. Detector settings are read from `config/detector_config.yaml`; they have no documented environment overrides.

Boolean environment values accept `1`, `true`, `yes`, or `on` as true. Examples below are safe placeholders where a committed default contains a routable address. None of the keys is a credential, but URLs, identifiers, face data, and stored images should still be handled as sensitive deployment information.

## Runtime configuration

| Key | Function | Required | Default | Example | Sensitive | Source file |
| --- | --- | ---: | --- | --- | ---: | --- |
| `app.db_path` / `CC_DB_PATH` | SQLite database path | Yes | `data/cc.db` | `data/field.db` | Yes | `config/runtime_config.yaml`, `src/app/orchestrator.py` |
| `app.log_dir` | Log directory created at startup | Yes | `logs` | `logs` | No | Same |
| `vehicle.vin` / `DS_VIN` | Event vehicle identifier | Yes | `VIN-0001` | `TEST-VEHICLE-01` | Yes | Same |
| `vehicle.dashboard_vehicle_id` | Default external vehicle ID | Yes | `1210` | `TEST-01` | Yes | Same |
| `camera.source` / `DS_CAMERA_SOURCE` | `opencv`, `picamera2`, or camera adapter `auto` | Yes | `opencv` | `opencv` | No | Same; `main.py`; `src/infrastructure/hardware/camera.py` |
| `camera.index` / `DS_CAMERA_INDEX` | OpenCV device index or `auto` | Yes | `auto` | `0` | No | Same |
| `DS_CAMERA_RES` | Camera resolution as `WIDTHxHEIGHT` | No | `640x480` | `1280x720` | No | `src/infrastructure/hardware/camera.py` |
| `identity.mode` / `DS_IDENTITY_MODE` | `enrollment` or `operation` | Yes | `enrollment` | `operation` | Yes | `config/runtime_config.yaml`, `src/app/orchestrator.py` |
| `DS_RECOGNITION_PATIENCE_SEC` | Unrecognized-user patience counter/threshold | No | `10` | `10` | No | `src/app/detection_loop.py` |
| `DS_FACE_RECOG_INTERVAL_SEC` | Face-recognition interval, seconds | No | `1.0` | `1.0` | No | Same |
| `DS_LOST_FACE_FRAMES` | Frames before active identity is dropped | No | `15` | `30` | No | Same |
| `DS_ID_RECHECK_SEC` | Active identity recheck interval, seconds | No | `8.0` | `8.0` | No | Same |
| `DS_ID_MISMATCH_MAX` | Consecutive mismatch limit | No | `4` | `4` | No | Same |
| `DS_FR_LOG_INTERVAL_SEC` | Face-recognition log throttle, seconds | No | `10.0` | `10` | No | `src/face_recognition/user_manager.py` |
| `DS_HEADLESS` | Disable GUI windows and keyboard controls | No | `0` | `1` | No | `src/app/detection_loop.py` |
| `DS_BUZZER_PIN` | Application buzzer BCM GPIO pin | No | `17` | `17` | No | Same |
| `DS_BUZZER_DISABLED` | Disable GPIO actuation | No | `0` | `1` | No | `src/infrastructure/hardware/buzzer.py` |
| `BUZZER_PIN` | Standalone buzzer-test pin | No | `17` | `17` | No | Same |
| `remote.drowsiness_enabled` / `DS_REMOTE_ENABLED` | Enable DMS event HTTP worker | No | `true` | `false` | No | `config/runtime_config.yaml`, `src/app/orchestrator.py` |
| `remote.include_image` / `DS_REMOTE_INCLUDE_IMAGE` | Include image with first event upload | No | `true` | `false` | Yes | Same; `src/logging/remote_logger.py` |
| `remote.image_max_width` / `DS_REMOTE_IMAGE_MAX_WIDTH` | Remote image maximum width, pixels | No | `480` | `480` | No | Same |
| `remote.image_jpeg_quality` / `DS_REMOTE_IMAGE_JPEG_QUALITY` | Remote retry JPEG quality | No | `60` | `60` | No | Same |
| `remote.retry_event_only_on_413` / `DS_REMOTE_RETRY_EVENT_ONLY_ON_413` | Retry metadata without image after HTTP 413 | No | `true` | `true` | No | Same |
| `remote.evidence_retry_enabled` / `DS_EVIDENCE_RETRY_ENABLED` | Retry unsent evidence | No | `true` | `true` | No | Same |
| `remote.evidence_retry_interval_sec` / `DS_EVIDENCE_RETRY_INTERVAL_SEC` | Evidence scan interval, seconds | No | `60` | `60` | No | Same |
| `remote.evidence_retry_backoff_sec` / `DS_EVIDENCE_RETRY_BACKOFF_SEC` | Evidence retry backoff, seconds | No | `300` | `300` | No | Same |
| `remote.evidence_retry_max_attempts` / `DS_EVIDENCE_RETRY_MAX_ATTEMPTS` | Maximum evidence attempts | No | `10` | `10` | No | Same |
| `DS_REMOTE_URL` | DMS API base URL | No | Committed development HTTP URL | `https://dms.example.invalid` | Yes | `src/api_client/config.py`, `src/app/orchestrator.py` |
| `DS_API_VERSION` | DMS endpoint version segment | No | `v1` | `v1` | No | `src/api_client/config.py` |
| `DS_REMOTE_TIMEOUT` | DMS HTTP timeout, seconds | No | `10` | `10` | No | Same |
| `gps.enabled` / `DS_GPS_ENABLED` | Enable serial GPS worker | No | `true` | `false` | No | `config/runtime_config.yaml`, `src/app/orchestrator.py` |
| `gps.port` / `DS_GPS_PORT` | Serial GPS device | When GPS enabled | `/dev/ttyAMA0` | `/dev/ttyUSB0` | No | Same |
| `gps.baud` / `DS_GPS_BAUD` | GPS serial baud rate | When GPS enabled | `9600` | `9600` | No | Same |
| `DS_GPS_POLL_INTERVAL_SEC` | Serial poll interval, seconds | No | `0.2` | `0.2` | No | `src/app/orchestrator.py`, `config/detector_config.yaml` |
| `gps.publish_enabled` / `DS_GPS_PUBLISH_ENABLED` | Enable GPS WebSocket publishing | No | `true` | `false` | No | `config/runtime_config.yaml`, `src/app/orchestrator.py` |
| `gps.vehicle_id` / `DS_GPS_VEHICLE_ID` | GPS payload vehicle ID | When publishing | `1210` | `TEST-01` | Yes | Same |
| `gps.ws_url` / `DS_GPS_WS_URL` | GPS WebSocket URL | When publishing | Committed development WS URL | `wss://gps.example.invalid/?vehicle_id=TEST-01&device=GPS` | Yes | Same |
| `DS_GPS_SEND_INTERVAL_SEC` | GPS publish interval, seconds | No | `2.0` | `2` | No | `src/app/orchestrator.py`, `config/detector_config.yaml` |
| `DS_GPS_WS_RECONNECT_INTERVAL_SEC` | WebSocket reconnect interval, seconds | No | `3.0` | `3` | No | Same |
| `compass.enabled` / `DS_COMPASS_ENABLED` | Enable compass | No | `true` | `false` | No | `config/runtime_config.yaml`, `src/app/orchestrator.py` |
| `compass.bus` / `DS_COMPASS_BUS` | I2C bus | When enabled | `1` | `1` | No | Same |
| `compass.address` / `DS_COMPASS_ADDRESS` | I2C address or `auto` | When enabled | `auto` | `0x0D` | No | Same |
| `compass.heading_offset_deg` / `DS_COMPASS_HEADING_OFFSET_DEG` | Heading mounting offset, degrees | No | `0` | `0` | No | Same |
| `compass.declination_deg` / `DS_COMPASS_DECLINATION_DEG` | Magnetic declination, degrees | No | `0` | `0` | No | Same |
| `compass.publish_enabled` / `DS_COMPASS_PUBLISH_ENABLED` | Enrich GPS payload with compass data | No | `true` | `false` | No | Same |
| `imu.enabled` / `DS_IMU_ENABLED` | Enable IMU worker | No | `false` | `false` | No | Same |
| `imu.bus` / `DS_IMU_BUS` | IMU I2C bus | When enabled | `1` | `1` | No | Same |
| `imu.address` / `DS_IMU_ADDRESS` | IMU I2C address or `auto` | When enabled | `auto` | `auto` | No | Same |
| `imu.sample_hz` / `DS_IMU_SAMPLE_HZ` | IMU sample rate, Hz | No | `25` | `25` | No | Same |
| `imu.publish_enabled` / `DS_IMU_PUBLISH_ENABLED` | Enable IMU HTTP publishing | No | `false` | `false` | No | Same |
| `imu.post_url` / `DS_IMU_POST_URL` | IMU/pothole HTTP URL | When publishing | Committed development HTTP URL | `https://telemetry.example.invalid/pothole` | Yes | Same |
| `imu.vehicle_id` / `DS_IMU_VEHICLE_ID` | IMU external vehicle ID | When publishing | `1210` | `TEST-01` | Yes | Same |
| `imu.send_interval_sec` / `DS_IMU_SEND_INTERVAL_SEC` | IMU publish interval, seconds | No | `1.0` | `1` | No | Same |
| `DS_IMU_TIMEOUT_SEC` | IMU POST timeout, seconds | No | `3.0` | `3` | No | `src/app/orchestrator.py`, `config/detector_config.yaml` |
| `imu.pothole_detection_enabled` / `DS_IMU_POTHOLE_DETECTION_ENABLED` | Enable candidate threshold evaluation | No | `false` | `false` | No | `config/runtime_config.yaml`, `src/app/orchestrator.py` |
| `imu.compat_payload` / `DS_IMU_COMPAT_PAYLOAD` | Use compatibility telemetry shape | No | `true` | `true` | No | Same |
| `DS_IMU_MIN_SPEED_KMPH` | Candidate minimum GPS speed, km/h | No | `5.0` | `5` | No | `src/app/orchestrator.py`, `config/detector_config.yaml` |
| `DS_IMU_ACCEL_MAG_THRESHOLD_G` | Candidate acceleration threshold, g | No | `1.8` | `1.8` | No | Same |
| `DS_IMU_JERK_MAG_THRESHOLD_GPS` | Candidate jerk threshold, g/s | No | `8.0` | `8` | No | Same |
| `DS_IMU_EVENT_COOLDOWN_SEC` | Candidate cooldown, seconds | No | `2.0` | `2` | No | Same |

## Detector configuration

All detector values below are in `config/detector_config.yaml`. Time values use seconds unless the key says `frames`.

| Key group | Keys and committed defaults | Function | Required | Sensitive | Source file |
| --- | --- | --- | ---: | ---: | --- |
| `system` | `vin: VIN-0001`, `target_fps: 30.0` | Detector VIN fallback and timing basis | Yes | VIN: Yes | `config/detector_config.yaml` |
| `detectors.pose_calibration` | `enabled: true`; `min_valid_frames: 20`; pitch/yaw/roll std: `3/4/4`; `face_confidence_min: 0.0` | Session head-pose baseline acceptance | Yes | No | Same |
| `detectors.drowsiness.perclos` | `window_sec: 10`; `threshold: 0.25` | Eye-closure proportion window | Yes | No | Same |
| `detectors.drowsiness.head_pose` | `pitch_abs_threshold_deg: 18.0` | Pitch contribution threshold | Yes | No | Same |
| `detectors.drowsiness.score` | on/off `0.68/0.55`; hold/release `0.5/0.4`; hard close `2.0`; yawn saturation `3`; weights PERCLOS/eyes/yawn/pitch `0.35/0.40/0.10/0.15` | Weighted-state hysteresis | Yes | No | Same |
| `detectors.drowsiness.episode` | start/end grace/minimum `0.5/1.5/2.0` | Episode lifecycle | Yes | No | Same |
| `detectors.drowsiness.ear` | low/high/drop `0.22/0.26/0.10`; drop window `15` frames; history `1.0` | Eye-aspect ratio state | Yes | No | Same |
| `detectors.drowsiness.blink` | closed frames min/max `1/10` | Blink classification | Yes | No | Same |
| `detectors.drowsiness.yawn` | threshold `0.27`; cooldown `2.0`; hand-cover distance `0.15`; frequency window/count `120/3`; timestamps max `10` | Yawn detection and frequency state | Yes | No | Same |
| `detectors.drowsiness.expression_suppression` | smile/laugh `15/20` frames | Expression-based suppression | Yes | No | Same |
| `detectors.drowsiness.severity.drowsiness` | medium/high/critical `2.0/3.0/5.0` | Duration severity boundaries | Yes | No | Same |
| `detectors.distraction.thresholds` | yaw `45.0`; pitch down/up `20.0/20.0` degrees | Head direction thresholds | Yes | No | Same |
| `detectors.distraction.timing` | hands visible `1.5`; gaze `1.2` | Distraction persistence | Yes | No | Same |
| `detectors.distraction.smoothing` | history/required frames `5/3`; face history/min samples `10/5`; partial-face `0.4` | Temporal smoothing and visibility | Yes | No | Same |
| `detectors.distraction.severity` | `long_duration_high_sec: 3.0` | High-severity duration boundary | Yes | No | Same |

The duplicate GPS/compass/IMU keys under `detector_config.yaml:system` act as fallbacks for selected values, while `runtime_config.yaml` is the primary runtime source. This duplication is a maintenance risk; do not assume changing every `system` sensor key changes runtime behavior without tracing `src/app/orchestrator.py`.
