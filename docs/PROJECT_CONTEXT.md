# Project Context

## Background and objective

This repository supports a plug-and-play Fleet Driver Monitoring System prototype intended for limited field validation on one TMMIN HiAce Commuter. The operational objective is to observe a driver through a cabin camera, detect configured indicators of drowsiness or visual distraction, provide an immediate local warning, and retain event evidence for later review.

The intended users are developers and designated fleet-validation personnel. Fleet operators may consume uploaded events through external backend/dashboard systems, but those systems are not contained in this repository.

> This system is a **limited field-validation prototype**. Repository evidence does not establish production readiness, safety certification, detection accuracy, or completed vehicle acceptance.

## System boundary

This is a single edge application, not a monorepo. Its boundary includes camera acquisition, driver/session handling, detection, local buzzer output, SQLite persistence, remote event upload, and optional GPS/compass/IMU workers. The remote HTTP API, GPS WebSocket service, dashboard, vehicle electrical installation, and operator response procedures are external.

## Capability status

### Current / Implemented

- OpenCV USB-camera and Picamera2 adapters, with OpenCV selected by `main.py` unless overridden.
- MediaPipe-based face mesh, hand, head-pose, and expression processing.
- Configured drowsiness and distraction detection rules.
- A local active-buzzer wrapper using `gpiozero`, with a non-fatal fallback when GPIO is unavailable.
- Enrollment mode, which stores a face encoding and calibrated eye threshold, and operation mode, which uses a session-only threshold without binding an identity.
- Local SQLite `users` and `events` tables, including JPEG evidence and remote-delivery state.
- Asynchronous HTTP upload of DMS events, event-only fallback after HTTP 413, and persistent metadata/evidence retry state.
- Optional serial GPS reading and WebSocket location publishing, with optional compass enrichment.
- Optional IMU reading and threshold-based pothole-candidate telemetry code; it is disabled by default.

### Under Validation / Improvement

- Camera mounting, framing, cabling, vibration resistance, thermal behavior, and GPIO reliability in the vehicle.
- Driver enrollment/recognition consistency and calibration behavior across drivers, eyewear, lighting, occlusion, and head positions.
- Detector thresholds and behavior under representative driving conditions.
- GPS fix reliability, compass calibration, sensor synchronization, external service compatibility, upload latency, retry/recovery behavior, and dashboard presentation.
- Optional IMU installation, baseline/calibration, candidate thresholds, and backend compatibility.
- Restart behavior and long-duration resource, storage, and network operation.

### Planned / Future

Driver Behaviour Monitoring analytics and an Emergency Response System are proposals only. See [Future Development](FUTURE_DEVELOPMENT.md).

## Current limitations and exclusions

- DMS event rows do not include latitude, longitude, trip ID, or a dashboard acknowledgement.
- GPS updates are published separately from DMS event uploads.
- No dependency lock/manifest, automated test suite, deployment unit, CI definition, acceptance report, benchmark, or supported Python/platform matrix is committed.
- The repository does not prove end-to-end backend/dashboard operation or provide their source.
- Automatic emergency notification, crash detection, driving-safety scoring, and production fleet administration are out of scope for the current application.

The repository history visible in files suggests incremental additions for remote evidence retry, compass/GPS publishing, and optional IMU telemetry. It does not contain a formal release history, so no milestone or acceptance claims are made here.
