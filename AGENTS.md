# Repository Guidance

This repository contains one Python edge Driver Monitoring System application.

## Important paths

- Entry point: `main.py`
- Runtime orchestration: `src/app/`
- Detection: `src/status/`, `src/core/`, and `src/mediapipe/`
- Hardware and persistence: `src/infrastructure/`
- Runtime and detector settings: `config/`
- Documentation: [`docs/`](docs/PROJECT_CONTEXT.md)

## Confirmed commands

- Run: `python main.py`
- Syntax/import-independent compile check: `python -m compileall -q main.py src`
- Hardware CLI discovery: `python -m src.gps.standalone_test --help`, `python -m src.compass.standalone_test --help`, and `python -m src.imu.standalone_test --help`

No dependency install, automated test, or lint command is committed. Do not invent one; see [`docs/SETUP_AND_RUN.md`](docs/SETUP_AND_RUN.md).

## Change rules

- Verify claims and commands against code or configuration.
- Label capabilities **Current / Implemented**, **Under Validation / Improvement**, or **Planned / Future**.
- Never describe Driver Behaviour Monitoring or the Emergency Response System as implemented.
- Never commit secrets, personal data, face encodings, real driver images, or production credentials.
- Keep the README concise and put operational detail in `docs/`.
- For code or documentation changes, update affected docs, preserve the status boundaries, run safe relevant checks, and confirm links and paths. Hardware and external integrations require explicit, controlled validation.
