# Fleet Driver Monitoring System

An edge application that uses a cabin camera to detect driver drowsiness and distraction, issue a local buzzer alert, store event evidence, and optionally publish data to external services.

> **Prototype status:** This repository is a **limited field-validation prototype** for one TMMIN HiAce Commuter. It is not a production-ready, certified, or fully validated safety system. It must not replace attentive driving or established fleet safety procedures.

## System overview

| Status | Capability |
| --- | --- |
| **Current / Implemented** | OpenCV or Picamera2 input; face/hand/head-pose processing; drowsiness and distraction rules; GPIO buzzer wrapper; local SQLite users and events; enrollment and identity-agnostic operation modes; event image evidence; asynchronous HTTP event upload with persistent retry state. |
| **Under Validation / Improvement** | Raspberry Pi and vehicle installation; driver identification consistency; detector behavior across drivers and conditions; GPS/compass capture and WebSocket publishing; remote event/evidence synchronization; connectivity recovery; long-duration operation; optional IMU/pothole telemetry. |
| **Planned / Future** | Driver Behaviour Monitoring analytics and an independently survivable Emergency Response System. These are designs, not current capabilities. |

The implemented high-level flow is:

`Cabin camera -> edge processing -> local buzzer -> SQLite event/evidence -> optional HTTP upload`

GPS/compass data follows a separate optional WebSocket path. The code does not currently attach GPS coordinates to DMS event records. The dashboard and backend are external; their source is not present here.

## Repository map

- `main.py` — application entry point.
- `src/app/` — startup orchestration and detection loop.
- `src/status/` and `src/mediapipe/` — detection rules and vision processing.
- `src/infrastructure/` — camera, buzzer, SQLite schema, and repositories.
- `src/logging/` and `src/api_client/` — local event logging and remote delivery.
- `src/gps/`, `src/compass/`, and `src/imu/` — optional sensor integrations.
- `config/` — runtime and detector configuration.
- `docs/` — detailed project and operational documentation.

## Prerequisites

- Python. The only inspected local environment uses Python 3.12.4; no supported version range is declared.
- A camera supported by OpenCV or Picamera2.
- Platform-specific hardware and packages for GPS, compass, IMU, or GPIO features when enabled.

The repository has no `requirements.txt`, `pyproject.toml`, or other reproducible dependency manifest. See [Setup and Run](docs/SETUP_AND_RUN.md) before creating a new environment.

## Quick start

From the repository root, using an environment whose dependencies are already installed:

```sh
python main.py
```

For a local camera-only check that avoids sensor connections and remote DMS uploads:

```sh
DS_GPS_ENABLED=0 DS_COMPASS_ENABLED=0 DS_IMU_ENABLED=0 DS_REMOTE_ENABLED=0 DS_BUZZER_DISABLED=1 python main.py
```

On PowerShell, set the variables separately with `$env:NAME = "value"`. The application is working when startup logs show the configuration summary and `System Ready`, then camera frames are processed. Press `q` in the application window to stop; use `Ctrl+C` in headless mode.

See [Setup and Run](docs/SETUP_AND_RUN.md) for the full procedure and limitations.

## Documentation

- [Project Context](docs/PROJECT_CONTEXT.md)
- [Setup and Run](docs/SETUP_AND_RUN.md)
- [Configuration](docs/CONFIGURATION.md)
- [Architecture and Data Flow](docs/ARCHITECTURE_AND_DATA_FLOW.md)
- [Validation and Known Issues](docs/VALIDATION_AND_KNOWN_ISSUES.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [Future Development](docs/FUTURE_DEVELOPMENT.md)

## Safety and privacy

This application can store face encodings and cabin images in a local SQLite database and can transmit event images when remote upload is enabled. Obtain appropriate consent, restrict database and network access, define retention rules, and use a secure deployment endpoint before field use. The endpoints committed in configuration are development defaults, not credentials or proof of a supported production service.
