import copy
import logging
import threading
import time
from typing import Optional

from src.gps.gps_service import GPSService
from src.gps.models import GPSState

log = logging.getLogger(__name__)


class GPSWorker:
    """
    Background GPS poller.
    Responsibility:
    - own GPSService
    - poll in background thread
    - keep latest state
    - optionally publish to dashboard via publisher
    """

    def __init__(
        self,
        port: str = "/dev/ttyAMA0",
        baud: int = 9600,
        poll_interval_sec: float = 0.2,
        publisher=None,
        send_interval_sec: float = 2.0,
        compass_service=None,
        compass_publish_enabled: bool = True,
        
    ):
        self.port = port
        self.baud = int(baud)
        self.poll_interval_sec = float(poll_interval_sec)
        self.publisher = publisher
        self.send_interval_sec = float(send_interval_sec)
        self.compass_service = compass_service
        self.compass_publish_enabled = bool(compass_publish_enabled)

        self.gps = GPSService(port=self.port, baud=self.baud)
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        self._latest_state = GPSState(source_port=self.port)
        self._connected = False
        self._last_send_ts = 0.0
        self._last_no_fix_log_ts = 0.0
        self._last_compass_warn_ts = 0.0
        self._gps_seq = 0

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return

        self.gps.connect()
        self._connected = True

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            daemon=True,
            name="GPSWorkerThread",
        )
        self._thread.start()

        log.info(
            "GPSWorker started (port=%s, baud=%s, poll_interval=%s)",
            self.port,
            self.baud,
            self.poll_interval_sec,
        )

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                state = self.gps.read()

                if state is not None:
                    if self.compass_service is not None and self.compass_publish_enabled:
                        self._attach_compass_state(state)

                    with self._lock:
                        self._latest_state = copy.deepcopy(state)

                    now = time.time()
                    should_send = (
                        self.publisher is not None
                        and state.gps_fix
                        and state.lat is not None
                        and state.lng is not None
                        and (now - self._last_send_ts) >= self.send_interval_sec
                    )
                    if self.publisher is not None and not state.gps_fix:
                        if (now - self._last_no_fix_log_ts) >= 5.0:
                            log.info(
                                "GPS waiting for fix (lat=%s lng=%s sats=%s hdop=%s)",
                                state.lat,
                                state.lng,
                                state.satellites,
                                state.hdop,
                            )
                            self._last_no_fix_log_ts = now

                    if should_send:
                        self._gps_seq += 1
                        state.ts_unix_ms = int(now * 1000)
                        state.seq = self._gps_seq

                        # Keep latest state updated with publish metadata too
                        with self._lock:
                            self._latest_state = copy.deepcopy(state)

                        ok = self.publisher.send_location(state)
                        if ok:
                            self._last_send_ts = now

            except Exception as e:
                log.warning("GPSWorker read loop error: %s", e, exc_info=True)

            time.sleep(self.poll_interval_sec)

    def get_latest(self) -> GPSState:
        with self._lock:
            return copy.deepcopy(self._latest_state)

    def has_fix(self) -> bool:
        with self._lock:
            return bool(self._latest_state.gps_fix)

    def is_connected(self) -> bool:
        return bool(self._connected)

    def _attach_compass_state(self, state: GPSState) -> None:
        try:
            compass_state = self.compass_service.read()
        except Exception as e:
            self._log_compass_warning("Compass read failed: %s", e)
            return

        if compass_state is None or compass_state.heading_deg is None:
            return

        state.heading_deg = float(compass_state.heading_deg)
        state.heading_source = compass_state.source
        state.compass_fix = bool(compass_state.compass_fix)
        state.mag_x = compass_state.mag_x
        state.mag_y = compass_state.mag_y
        state.mag_z = compass_state.mag_z
        state.compass_chip = compass_state.chip
        state.compass_address = compass_state.address

    def _log_compass_warning(self, message: str, *args) -> None:
        now = time.time()
        if (now - self._last_compass_warn_ts) >= 5.0:
            log.warning(message, *args)
            self._last_compass_warn_ts = now

    def close(self) -> None:
        self._stop_event.set()

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

        try:
            self.gps.close()
        except Exception:
            pass

        self._connected = False
        log.info("GPSWorker stopped")
