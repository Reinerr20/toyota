# Validation and Known Issues

## Validation evidence

No formal field-test report, acceptance criteria, performance benchmark, CI run, or automated test suite is committed. The following evidence is limited to repository inspection and safe non-hardware checks; it is not vehicle validation.

| Item | Test condition | Method | Expected result | Observed result | Evidence source | Limitation |
| --- | --- | --- | --- | --- | --- | --- |
| Python syntax | Inspected local Python 3.12.4 virtual environment | `python -m compileall -q main.py src` | All Python files compile | Passed during documentation audit | Command output; Python sources | Does not import dependencies or execute behavior |
| YAML parsing | Current committed configuration | Parse both YAML files with PyYAML | Both load as mappings | Passed during documentation audit | `config/*.yaml` | Does not validate semantics or hardware suitability |
| Diagnostic CLIs | Inspected local virtual environment | Run GPS, compass, and IMU modules with `--help` | Argument help exits successfully | Passed during documentation audit | Standalone modules | Does not access or validate sensors |
| Runtime configuration helper | Current source and YAML | Construct `RuntimeConfig` and read representative values | Config resolves from repository root | Passed during documentation audit | `src/utils/config/runtime_config.py` | Does not cover every override or invalid input |
| Static documentation integrity | Updated Markdown set | Check relative links and referenced repository paths | All local targets resolve | Passed during documentation audit | Documentation-link check | Cannot validate external services |

The standalone sensor scripts and local SQLite files indicate development activity, but their presence is not evidence of successful field validation. Existing database contents are not treated as acceptance evidence because test conditions and provenance are not documented.

## Known issues

| Area | Current symptom | Operational impact | Current status | Workaround | Recommended next validation |
| --- | --- | --- | --- | --- | --- |
| Dependency installation | A bootstrap command now records the inspected environment, but no committed manifest or supported version matrix exists | Raspberry Pi compatibility and clean-environment reproducibility remain unproven | **Under Validation / Improvement** | Use the documented bootstrap as a reference and record platform-specific failures; do not substitute versions silently | Commit and test a reviewed dependency manifest on every supported target |
| Deployment | No service unit or deployment package is committed | Boot/autorestart instructions cannot be applied verbatim | **Under Validation / Improvement** | Run manually from an activated environment | Validate a least-privilege unit with device, network, and restart controls |
| Default network configuration | Plain HTTP/WS development addresses and generic vehicle IDs are committed | Misrouting, exposure, or accidental traffic is possible | **Under Validation / Improvement** | Disable publishers locally and override endpoints/IDs in controlled deployment configuration | Verify TLS, authentication, authorization, endpoint ownership, and identifier provisioning |
| Privacy | Face encodings and cabin JPEGs are stored in SQLite; images may be uploaded | Personal data can be exposed or retained too long | **Under Validation / Improvement** | Restrict filesystem/network access and disable images/uploads when unnecessary | Define consent, retention, encryption, deletion, and access-audit controls |
| Identity mode | YAML defaults to enrollment; README previously implied operation-style use | Unintended new user registration can occur | **Under Validation / Improvement** | Explicitly set `DS_IDENTITY_MODE=operation` when enrollment is not intended | Test user changeover, mismatch, eyewear, lighting, and deletion workflows |
| DMS and GPS association | DMS event schema has no coordinates or trip ID | Dashboard cannot reliably correlate an event to location from this payload alone | **Under Validation / Improvement** | Correlate external streams by controlled timestamps only, with limitations recorded | Specify and test a single event/trip correlation contract |
| Offline behavior | DMS events have persistent retry state; GPS has reconnect but no durable queue | Location updates can be lost during outages | **Under Validation / Improvement** | Treat GPS as live telemetry, not an audit log | Test outage duration, reconnection, ordering, duplication, and storage bounds |
| Event evidence | Metadata may succeed while image evidence remains pending or exhausts retries | Review can receive an event without its image | **Under Validation / Improvement** | Inspect separate metadata/evidence state columns | Exercise HTTP 413, timeout, server error, retry exhaustion, and recovery |
| Camera/hardware installation | No mounting, framing, cable, vibration, thermal, or power evidence is committed | Unstable capture or device resets can degrade detection | **Under Validation / Improvement** | Perform stationary preflight checks and secure installation | Run documented thermal, vibration, power interruption, and long-duration trials |
| Detector performance | Thresholds exist without labeled-dataset metrics or field acceptance results | False alerts and missed indicators are unquantified | **Under Validation / Improvement** | Treat output as advisory during controlled validation | Define representative scenarios, ground truth, metrics, and acceptance criteria |
| Buzzer fallback | Missing `gpiozero`/GPIO access leaves a no-op buzzer while the app continues | Local warning may be absent | **Under Validation / Improvement** | Confirm startup logs and run a safe standalone GPIO check | Add and validate a health indication/fail-state procedure |
| Configuration duplication | Some sensor defaults exist in both runtime and detector YAML files | Operators may edit a value that is not the active source | **Under Validation / Improvement** | Follow `src/app/orchestrator.py` resolution and this configuration guide | Consolidate configuration in a future code change with regression tests |
| Optional IMU/pothole logic | Disabled by default and lacks calibration/acceptance evidence | Candidates cannot be treated as validated road events | **Under Validation / Improvement** | Keep disabled outside controlled tests | Calibrate orientation/baseline and validate against labeled routes and surfaces |
| Long-duration operation | No soak-test record, database retention limit, or disk-pressure policy | Memory, storage, or thread/network degradation may emerge | **Under Validation / Improvement** | Monitor logs, database size, process health, and disk space | Run a documented soak test with outage/restart/storage scenarios |

Human-supplied installation records, approved dependency versions, backend/dashboard contracts, privacy requirements, and field-validation results are needed to close these gaps.
