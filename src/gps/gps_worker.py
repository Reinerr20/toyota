import threading
import time
import json
import logging
import websocket

from src.gps.gps_service import GPSService

log = logging.getLogger(__name__)


class GPSWorker:
    SEND_INTERVAL = 2.0
    WS_RETRY_INTERVAL = 3.0

    def __init__(
        self,
        vehicle_id: int = 999,
        ws_url: str = "ws://203.100.57.59:3300/?vehicle_id=999&device=GPS",
        port: str = "/dev/ttyAMA10",
        baud: int = 115200,
    ):
        self.vehicle_id = vehicle_id
        self.ws_url = ws_url
        self.port = port
        self.baud = baud

        self._stop_event = threading.Event()
        self._thread = None
        self._ws = None

        self.gps = GPSService(port=port, baud=baud)

    def start(self):
        self.gps.connect()

        self._thread = threading.Thread(
            target=self._run,
            daemon=True,
            name="GPSWorkerThread",
        )
        self._thread.start()

        log.info(
            "GPSWorker started (vehicle_id=%s, port=%s, baud=%s)",
            self.vehicle_id,
            self.port,
            self.baud,
        )

    def _connect_ws(self):
        try:
            ws = websocket.create_connection(self.ws_url)
            log.info("GPS WebSocket connected: %s", self.ws_url)
            return ws
        except Exception as e:
            log.error("WebSocket connection failed: %s", e)
            return None

    def _build_live_payload(self, data: dict) -> dict:
        return {
            "event": "UPDATE_LOCATION",
            "target": "DASHBOARD",
            "vehicle_id": str(self.vehicle_id),
            "gps_lat": data["lat"],
            "gps_lng": data["lng"],
        }

    def _run(self):
        last_send = 0.0
        last_ws_attempt = 0.0

        while not self._stop_event.is_set():
            now = time.time()

            # Reconnect WS if needed
            if self._ws is None and now - last_ws_attempt >= self.WS_RETRY_INTERVAL:
                last_ws_attempt = now
                self._ws = self._connect_ws()

            data = self.gps.read()

            # Only send if GPS has valid coordinates and interval elapsed
            if (
                data
                and data.get("lat") is not None
                and data.get("lng") is not None
                and self._ws is not None
                and now - last_send >= self.SEND_INTERVAL
            ):
                payload = self._build_live_payload(data)

                try:
                    self._ws.send(json.dumps(payload))
                    log.info("GPS sent: %s", payload)
                    last_send = now
                except Exception as e:
                    log.error("GPS send failed: %s", e)
                    try:
                        self._ws.close()
                    except Exception:
                        pass
                    self._ws = None

            time.sleep(0.1)

    def close(self):
        self._stop_event.set()

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)

        if self._ws:
            try:
                self._ws.close()
            except Exception:
                pass
            self._ws = None

        self.gps.close()
        log.info("GPSWorker stopped")


if __name__ == "__main__":
    print("gps_worker main entered")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    worker = GPSWorker()
    print("worker created")
    worker.start()
    print("worker started")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        worker.close()