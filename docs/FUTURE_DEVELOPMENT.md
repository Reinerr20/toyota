# Future Development

Everything in this document is **Planned / Future**. It is not part of current-system acceptance and must not be represented as implemented or validated.

## Driver Behaviour Monitoring and analytics

### Objective and distinction

The current DMS uses a cabin camera to assess visible driver condition and attention. Proposed Driver Behaviour Monitoring would instead use vehicle dynamics to identify motion patterns and summarize trips.

An initial proof of concept could explore harsh braking, harsh acceleration, harsh cornering, trip-based behavior summaries, and history associated with driver/session, vehicle, time, GPS, and trip. It must not claim overtaking detection, unsafe lane-change detection, or a validated driving-safety score; those require additional sensing, road context, calibration, and validation.

### Proposed architecture

`6-axis IMU -> calibrated vehicle-frame samples -> motion features -> candidate event rules -> trip/event store -> backend/reporting`

GPS would provide supporting speed, location, route, and trip context. A 6-axis IMU would be the primary source for vehicle dynamics. The repository's optional IMU reader, GPS worker, configuration pattern, vehicle identifier, worker lifecycle, HTTP publisher, and SQLite/outbox concepts may be reusable, but the existing pothole-candidate code is not a validated behavior-monitoring implementation.

### Proposed additions

- Hardware: fixed-orientation 6-axis IMU, reviewed mounting, stable power, and optional higher-quality GNSS.
- Data: event ID/type, event and sample timestamps, vehicle/driver/session/trip IDs, latitude/longitude/speed/course, acceleration and angular-rate axes, derived magnitudes, calibration/version metadata, confidence/quality flags, and delivery state.
- Integration: a versioned local event schema, durable queue, authenticated backend contract, trip lifecycle source, and dashboard/report definitions.
- Calibration: sensor bias/noise, gravity removal, axes-to-vehicle transformation, sample timing, mounting change detection, speed gating, and vehicle/load-specific thresholds.
- Validation: labeled maneuvers on a controlled route, driver/vehicle/load/surface variation, GPS outage and clock tests, false-event review, reproducibility, and threshold/version traceability.
- Risks: mounting drift, road-surface confusion, GPS lag, time misalignment, sensor saturation, per-vehicle variation, privacy, alert fatigue, and unsupported safety conclusions.

Explicit exclusions for the initial PoC are lane-level interpretation, overtaking classification, collision determination, automated disciplinary scoring, and claims that inferred behavior proves driver intent.

## Emergency Response System

### Objective and boundary

The proposed Emergency Response System (ERS) is a separate emergency layer, not a second DMS. It should have minimum independent operation and must not depend entirely on the main DMS Raspberry Pi.

```text
Potential Emergency -> Local Verification -> Occupant Response Window -> Internal Alert -> Acknowledgement -> Follow-Up Record
```

Possible future triggers include manual SOS, potential impact from a dedicated IMU, power interruption combined with supporting signals, a multi-signal abnormal condition, and DMS information used only as supporting context.

### Proposed emergency package

- Vehicle ID and timestamp.
- GPS location and quality/freshness.
- Trigger source and evidence/quality indicators.
- Main and backup power status.
- Occupant response status and response-window timing.
- Alert delivery status, recipient route, acknowledgement status/time, and follow-up record ID.

### Proposed design and integration

- A dedicated controller or communications path with monitored backup power, local manual input, occupant prompt/cancel interface, and health reporting.
- A durable, authenticated alert state machine with deduplication, escalation policy, retries, acknowledgements, and audit history.
- An internal fleet-operator or designated-contact endpoint for initial validation.
- Optional read-only context from DMS, GPS, and vehicle identity; ERS must define behavior when each is unavailable.

### Validation needs and risks

Validate trigger simulations without real emergency dispatch, false-trigger cancellation, missed/late acknowledgement, network and main-power loss, location staleness, duplicate suppression, backup-power duration, contact availability, privacy/access controls, and operator procedures. Independent safety and legal review is required before any live emergency workflow.

Key risks are false or missed triggers, depleted backup power, network coverage, ambiguous occupant response, stale position, alert duplication, unauthorized disclosure, unclear operator responsibility, and user overreliance.

ERS must not be described as certified eCall, an automatic police/ambulance connection, a medical diagnostic system, guaranteed crash detection, or a production-ready emergency service.
