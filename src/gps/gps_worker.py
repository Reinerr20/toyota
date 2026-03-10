import threading
import time
import json
import logging
import websocket

from src.gps.gps_service import GPSService

print("gps_worker.py loaded")

log = logging.getLogger(__name__)


class GPSWorker:
    SEND_INTERVAL = 2.0

    def __init__(self, vehicle_id: int = 999,
                 ws_url: str = "ws://203.100.57.59:3300/?vehicle_id=999&device=GPS",
                 port: str = "/dev/ttyAMA10", baud: int = 115200):
    
        self.vehicle_id = vehicle_id
        self.ws_url = ws_url

        self._stop_event = threading.Event()
        self._thread = None

        self.gps = GPSService(port=port, baud=baud)

    def start(self):
        self.gps.connect()

        self._thread = threading.Thread(
            target=self._run,
            daemon=True
        )
        self._thread.start()

        log.info("GPSWorker started")

    def _connect_ws(self):
        try:
            ws = websocket.create_connection(self.ws_url)
            log.info("GPS WebSocket connected")
            return ws
        except Exception as e:
            log.error("WebSocket connection failed: %s", e)
            return None

    def _run(self):
        ws = None
        last_send = 0

        while not self._stop_event.is_set():

            if ws is None:
                ws = self._connect_ws()
                time.sleep(1)
                continue

            data = self.gps.read()
            now = time.time()

            if data and now - last_send > self.SEND_INTERVAL:
                payload = dict(data)
                payload["millis"] = int(now * 1000)

                try:
                    ws.send(json.dumps(payload))
                    log.info("GPS sent: %s", payload)
                    last_send = now
                except Exception:
                    ws = None

            time.sleep(0.1)

    def close(self):
        self._stop_event.set()

        if self._thread:
            self._thread.join()

        self.gps.close()
        log.info("GPSWorker stopped")


if __name__ == "__main__":
    print("gps_worker main entered")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
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