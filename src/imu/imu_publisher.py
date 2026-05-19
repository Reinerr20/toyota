import logging
from typing import Optional

log = logging.getLogger(__name__)


class IMUPublisher:
    """Short-timeout HTTP publisher for pothole telemetry payloads."""

    def __init__(
        self,
        post_url: str,
        vehicle_id: str,
        timeout_sec: float = 3.0,
        enabled: bool = True,
    ):
        self.post_url = post_url
        self.vehicle_id = str(vehicle_id)
        self.timeout_sec = float(timeout_sec)
        self.enabled = bool(enabled)
        self._session: Optional[object] = None

        try:
            import requests  # type: ignore

            self._session = requests.Session()
        except Exception as e:
            log.warning("IMU publisher requests unavailable: %s", e)
            self._session = None

    def send_payload(self, payload: dict) -> bool:
        if not self.enabled:
            return False
        if self._session is None:
            log.warning("IMU payload send failed: requests session unavailable")
            return False

        try:
            response = self._session.post(
                self.post_url,
                json=payload,
                timeout=self.timeout_sec,
            )
            response.raise_for_status()
            log.info("IMU payload sent")
            return True
        except Exception as e:
            log.warning("IMU payload send failed: %s", e)
            return False

    def close(self) -> None:
        session = self._session
        self._session = None
        if session is not None:
            try:
                session.close()
            except Exception:
                pass

