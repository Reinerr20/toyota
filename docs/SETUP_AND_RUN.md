# Setup and Run

## Supported environment evidence

The application is Python-based and contains Linux/Raspberry Pi hardware paths. The inspected developer virtual environment uses Python 3.12.4 on Windows, but that environment is untracked and is not a declared compatibility guarantee. Raspberry Pi is the intended hardware target inferred from Picamera2, GPIO, I2C, serial-device, and systemd references.

There is no committed dependency manifest. The commands below reproduce the direct Python packages found in the inspected Python 3.12.4 developer environment; they are a documented bootstrap reference, not a supported-version guarantee. Raspberry Pi, Picamera2, MediaPipe, and PyTorch wheel availability varies by OS, CPU architecture, and Python version.

## Install the software dependencies

### Windows or Linux development environment

This copy-paste block creates a virtual environment and installs all direct third-party packages imported by the current application. It uses one OpenCV distribution (`opencv-contrib-python`) to avoid installing two packages that both provide `cv2`.

PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install numpy==1.26.4 opencv-contrib-python==4.11.0.86 PyYAML==6.0.3 mediapipe==0.10.21 torch==2.2.2 torchvision==0.17.2 facenet-pytorch==2.6.0 Pillow==10.2.0 requests==2.32.5 websocket-client==1.9.0 pyserial==3.5 pynmea2==1.19.0 gpiozero==2.0.1
```

POSIX shell:

```sh
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install numpy==1.26.4 opencv-contrib-python==4.11.0.86 PyYAML==6.0.3 mediapipe==0.10.21 torch==2.2.2 torchvision==0.17.2 facenet-pytorch==2.6.0 Pillow==10.2.0 requests==2.32.5 websocket-client==1.9.0 pyserial==3.5 pynmea2==1.19.0 gpiozero==2.0.1 smbus2==0.6.1
```

Package roles:

| Package | Used for |
| --- | --- |
| `numpy`, `opencv-contrib-python` | Frames, image operations, JPEG evidence, and UI |
| `PyYAML` | Runtime and detector configuration |
| `mediapipe` | Face mesh and hand landmarks |
| `torch`, `torchvision`, `facenet-pytorch`, `Pillow` | MTCNN face detection and FaceNet identity embeddings |
| `requests` | DMS and optional IMU HTTP publishing |
| `websocket-client` | GPS dashboard publishing |
| `pyserial`, `pynmea2` | Serial GPS and NMEA parsing |
| `gpiozero` | Raspberry Pi buzzer GPIO |
| `smbus2` | I2C compass and IMU access |

The first use of `InceptionResnetV1(pretrained="vggface2")` may need network access to download pretrained weights into the local PyTorch cache. For an offline vehicle, initialize the model once in an approved connected environment and provision the resulting cache according to the project's artifact policy.

### Raspberry Pi OS additions

Install operating-system support before the Python packages:

```sh
sudo apt update
sudo apt install -y python3-venv python3-pip python3-dev python3-picamera2 python3-gpiozero libgl1 libglib2.0-0 libcap-dev i2c-tools
python3 -m venv --system-site-packages .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install numpy==1.26.4 opencv-contrib-python==4.11.0.86 PyYAML==6.0.3 mediapipe==0.10.21 torch==2.2.2 torchvision==0.17.2 facenet-pytorch==2.6.0 Pillow==10.2.0 requests==2.32.5 websocket-client==1.9.0 pyserial==3.5 pynmea2==1.19.0 smbus2==0.6.1
```

`--system-site-packages` makes the Raspberry Pi OS Picamera2 and gpiozero packages visible inside the virtual environment. Do not install Picamera2 from an arbitrary PyPI package in place of the Raspberry Pi OS package.

The final pip command is verified against the inspected Windows environment, not on Raspberry Pi hardware. If pip reports that MediaPipe, Torch, or Torchvision has no compatible distribution, stop and record the Pi model, OS release, CPU architecture, Python version, and error. Do not silently substitute unrelated versions; the project owner must approve and validate an architecture-compatible dependency set.

### Confirm the installation

Run this core import check before connecting hardware or enabling network publishers:

```sh
python -c "import cv2, numpy, yaml, mediapipe, torch, torchvision, facenet_pytorch, PIL, requests, websocket, serial, pynmea2, gpiozero; print('Core application dependencies imported successfully')"
```

On Raspberry Pi, also verify the OS-provided camera package and Linux-only I2C package:

```sh
python -c "import picamera2, smbus2; print('Raspberry Pi camera and I2C dependencies imported successfully')"
```

`smbus2` is intentionally excluded from the Windows command because it imports the Linux-only `fcntl` interface. This does not affect a Windows camera-only run while compass and IMU features are disabled.

## Hardware prerequisites

- Cabin-facing USB camera or Raspberry Pi camera module.
- Active buzzer wired to the configured BCM GPIO pin when audible alerts are enabled.
- Optional GPS receiver available as a serial device.
- Optional supported I2C compass and IMU. Detection logic in `src/compass/compass_service.py` and `src/imu/imu_service.py` determines supported chips/addresses.
- Stable vehicle-safe power, mounting, cooling, and network access for field validation.

Do not perform vehicle or hardware validation without an approved wiring plan, installation review, and a safe stationary test environment.

## Prepare configuration

1. Clone or copy the repository and enter its root (the directory containing `main.py`).
2. Create and activate the appropriate virtual environment using the installation block above.
3. Run the dependency import check. Record any platform-specific substitution needed for Raspberry Pi review.
4. Review `config/runtime_config.yaml` and `config/detector_config.yaml`.
5. Replace vehicle identifiers and development network endpoints for the intended controlled environment. Do not commit secrets or production credentials.
6. For the first local check, disable all external and hardware-dependent optional services.

Configuration priority is environment variable, then `config/runtime_config.yaml`, then the code fallback. Detector thresholds come from `config/detector_config.yaml`. See [Configuration](CONFIGURATION.md).

## Development or local camera check

This mode does not validate Raspberry Pi hardware, GPIO, GPS, backend, or dashboard behavior.

On a POSIX shell:

```sh
DS_CAMERA_SOURCE=opencv DS_CAMERA_INDEX=0 DS_GPS_ENABLED=0 DS_COMPASS_ENABLED=0 DS_IMU_ENABLED=0 DS_REMOTE_ENABLED=0 DS_BUZZER_DISABLED=1 python main.py
```

On PowerShell:

```powershell
$env:DS_CAMERA_SOURCE = "opencv"
$env:DS_CAMERA_INDEX = "0"
$env:DS_GPS_ENABLED = "0"
$env:DS_COMPASS_ENABLED = "0"
$env:DS_IMU_ENABLED = "0"
$env:DS_REMOTE_ENABLED = "0"
$env:DS_BUZZER_DISABLED = "1"
python main.py
```

Expected observable behavior:

1. Logs identify `config/runtime_config.yaml`, the database path, camera settings, identity mode, and optional-service states.
2. The camera opens; otherwise startup ends with `Camera failed to open`.
3. Logs show `System Ready` and the detection loop processes frames.
4. In GUI mode, press `q` to stop. In headless mode (`DS_HEADLESS=1`), use `Ctrl+C` or send SIGINT/SIGTERM.
5. Cleanup stops workers, closes the SQLite connection, releases the camera, and turns the buzzer off through signal/cleanup handling.

The default `identity.mode` in `config/runtime_config.yaml` is `enrollment`, which may store a new face encoding after calibration. Use `DS_IDENTITY_MODE=operation` for an identity-agnostic session that does not register a new user.

## Raspberry Pi or in-vehicle operation

1. Confirm camera access independently:

   ```sh
   python -m src.infrastructure.hardware.camera
   ```

2. Select the camera source: `DS_CAMERA_SOURCE=opencv` for USB or `DS_CAMERA_SOURCE=picamera2` for a Pi camera.
3. Validate the buzzer only in a safe stationary hardware test. The standalone script is interactive and actuates GPIO:

   ```sh
   BUZZER_PIN=17 python src/infrastructure/hardware/buzzer.py
   ```

4. Validate optional sensors before enabling them in the application:

   ```sh
   python -m src.gps.standalone_test --port /dev/ttyAMA0 --baud 9600
   python -m src.compass.standalone_test
   python -m src.imu.standalone_test
   ```

5. Configure controlled external endpoints, then run `python main.py`. Use `DS_HEADLESS=1` for a displayless process.

These commands prove only that a diagnostic entry point exists. No hardware was available during this documentation audit.

## Verification

Use Python's SQLite module if the `sqlite3` CLI is unavailable:

```sh
python -c "import sqlite3; c=sqlite3.connect('data/cc.db'); print(c.execute('SELECT id,time,status,user_id,remote_sent,evidence_sent FROM events ORDER BY id DESC LIMIT 10').fetchall())"
```

An event row confirms local persistence. Nonzero image length (query `length(img_drowsiness)`) confirms stored evidence. `remote_sent = 1` and `evidence_sent = 1` are local delivery-state indicators, not independent proof that a dashboard rendered the data.

## Restart and recovery

1. Stop with `q`, `Ctrl+C`, SIGINT, or SIGTERM and wait for shutdown logs.
2. Correct the camera, sensor, configuration, storage, or network problem.
3. Restart with the same reviewed configuration.
4. When remote upload is enabled, the worker scans unsent SQLite events in batches and retries. Do not delete or replace `data/cc.db` during recovery.

## Service/autostart status

No `.service` unit is committed, so exact systemd installation is unresolved. `systemd_service_guide.txt` is retained only as a pointer to this limitation. Do not use its former machine-specific example as a deployable unit. A production service definition needs reviewed `User`, `WorkingDirectory`, `ExecStart`, environment handling, device permissions, network ordering, restart limits, and log/storage policy.

For safe device shutdown, stop the application first, verify that camera/sensor workers have closed, then use the operating system's normal shutdown procedure. Do not remove vehicle power while SQLite is writing.
