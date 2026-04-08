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
    - expose latest GPS snapshot safely

    No websocket.
    No DB.
    No dashboard transport.
    """

    def __init__(
        self,
        port: str = "/dev/ttyAMA0",
        baud: int = 9600,
        poll_interval_sec: float = 0.2,
    ):
        self.port = port
        self.baud = int(baud)
        self.poll_interval_sec = float(poll_interval_sec)

        self.gps = GPSService(port=self.port, baud=self.baud)
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        self._latest_state = GPSState(source_port=self.port)
        self._connected = False

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
                    with self._lock:
                        self._latest_state = copy.deepcopy(state)
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