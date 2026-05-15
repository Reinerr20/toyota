import json
import logging
import threading
import time
from typing import Optional
from datetime import datetime

import websocket

from src.gps.models import GPSState

log = logging.getLogger(__name__)


def _ms_to_readable_local(ms: int) -> str:
    dt = datetime.fromtimestamp(ms / 1000)
    return dt.strftime("%Y-%m-%d %H:%M:%S.") + f"{dt.microsecond // 1000:03d} WIB"

class GPSPublisher:
    """
    WebSocket publisher for live GPS dashboard updates.
    Responsibility:
    - maintain WS connection
    - reconnect when needed
    - send live GPS payload

    No serial parsing.
    No threading loop ownership.
    """

    def __init__(
        self,
        vehicle_id: str,
        ws_url: str,
        reconnect_interval_sec: float = 3.0,
    ):
        self.vehicle_id = str(vehicle_id)
        self.ws_url = ws_url
        self.reconnect_interval_sec = float(reconnect_interval_sec)

        self._ws = None
        self._lock = threading.Lock()
        self._last_connect_attempt = 0.0

    def _connect(self) -> bool:
        now = time.time()
        if (now - self._last_connect_attempt) < self.reconnect_interval_sec:
            return False

        self._last_connect_attempt = now

        try:
            ws = websocket.create_connection(self.ws_url, timeout=5)
            with self._lock:
                self._ws = ws
            log.info("GPS WebSocket connected: %s", self.ws_url)
            return True
        except Exception as e:
            log.warning("GPS WebSocket connection failed: %s", e)
            return False

    def _ensure_connected(self) -> bool:
        with self._lock:
            ws_ok = self._ws is not None
        if ws_ok:
            return True
        return self._connect()

    def _build_payload(self, state: GPSState) -> dict:
        # Start with exact old format for compatibility
        payload = {
            "event": "UPDATE_LOCATION",
            "target": "DASHBOARD",
            "vehicle_id": self.vehicle_id,
            "gps_lat": state.lat,
            "gps_lng": state.lng,
        }

        # Optional extras (usually safe if backend ignores unknown keys)
        if state.speed_kmph is not None:
            payload["speed_kmph"] = state.speed_kmph
        if state.satellites is not None:
            payload["satellites"] = state.satellites
        if state.hdop is not None:
            payload["hdop"] = state.hdop
        if state.gps_fix is not None:
            payload["gps_fix"] = state.gps_fix
        if state.ts_unix_ms is not None:
            payload["ts_unix_ms"] = state.ts_unix_ms
            payload["ts_readable"] = _ms_to_readable_local(state.ts_unix_ms)

        if state.gps_read_ts_unix_ms is not None:
            payload["gps_read_ts_unix_ms"] = state.gps_read_ts_unix_ms
            payload["gps_read_ts_readable"] = _ms_to_readable_local(state.gps_read_ts_unix_ms)

        if state.seq is not None:
            payload["seq"] = state.seq

        if state.heading_deg is not None:
            payload["heading_deg"] = state.heading_deg
            log.info("GPS payload includes heading_deg=%s", state.heading_deg)
        if state.heading_source is not None:
            payload["heading_source"] = state.heading_source
        if state.compass_fix:
            payload["compass_fix"] = state.compass_fix
        if state.compass_chip is not None:
            payload["compass_chip"] = state.compass_chip
        if state.compass_address is not None:
            payload["compass_address"] = state.compass_address
        if state.mag_x is not None:
            payload["mag_x"] = state.mag_x
        if state.mag_y is not None:
            payload["mag_y"] = state.mag_y
        if state.mag_z is not None:
            payload["mag_z"] = state.mag_z

        return payload

    def send_location(self, state: GPSState) -> bool:
        if state is None:
            return False

        if state.lat is None or state.lng is None:
            return False

        if not self._ensure_connected():
            return False

        payload = self._build_payload(state)

        try:
            with self._lock:
                self._ws.send(json.dumps(payload))
            log.info("GPS WS sent: %s", payload)
            return True
        except Exception as e:
            log.warning("GPS WS send failed: %s", e)
            self.close()
            return False

    def close(self) -> None:
        with self._lock:
            ws = self._ws
            self._ws = None

        if ws is not None:
            try:
                ws.close()
            except Exception:
                pass

        log.info("GPS WebSocket closed")
