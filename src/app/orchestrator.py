import logging
import cv2
import yaml
import os
from pathlib import Path

from src.infrastructure.hardware.camera import Camera
from src.face_recognition.user_manager import UserManager
from src.logging.remote_logger import RemoteLogWorker
from src.logging.system_logger import SystemLogger
from src.infrastructure.data.database import UnifiedDatabase
from src.infrastructure.data.repository import UnifiedRepository
from src.app.detection_loop import DetectionLoop
from src.gps.gps_worker import GPSWorker

log = logging.getLogger(__name__)

class DrowsinessSystem:
    CONFIG_PATH = "config/detector_config.yaml"
    DB_PATH = os.getenv("CC_DB_PATH", os.path.join("data", "cc.db"))

    def __init__(self):
        self._ensure_paths()
        self.config = self._load_config()
        sys_cfg = self.config.get('system', {})
        self.vin = sys_cfg.get('vin', os.getenv('DS_VIN', 'VIN-0001'))
        self.fps = float(sys_cfg.get('target_fps', 30.0))
        self.gps_enabled = bool(sys_cfg.get('gps_enabled', True))
        self.gps_port = sys_cfg.get('gps_port', os.getenv('DS_GPS_PORT', '/dev/ttyAMA10'))
        self.gps_baud = int(sys_cfg.get('gps_baud', os.getenv('DS_GPS_BAUD', '115200')))
        self.gps_vehicle_id = int(sys_cfg.get('gps_vehicle_id', os.getenv('DS_GPS_VEHICLE_ID', '999')))
        self.gps_ws_url = sys_cfg.get(
    'gps_ws_url',
    os.getenv('DS_GPS_WS_URL', f'ws://203.100.57.59:3300/?vehicle_id={self.gps_vehicle_id}&device=GPS')
)

    def run(self):
        try:
            self._init_resources()
            log.info(f"System Ready. VIN: {self.vin}")
            print("\n>>> PRESS 'Q' TO EXIT <<<\n")

            DetectionLoop(
                camera=self.camera,
                user_manager=self.user_manager,
                system_logger=self.system_logger,
                vehicle_vin=self.vin,
                fps=self.fps,
                detector_config_path=self.CONFIG_PATH,
            ).run()

        except KeyboardInterrupt:
            log.info("User requested shutdown.")
        except Exception as e:
            log.error(f"Fatal: {e}", exc_info=True)
        finally:
            self._cleanup()

    def _init_resources(self):
        # 1. Unified Database & Repository
        self.db = UnifiedDatabase(self.DB_PATH)
        self.repo = UnifiedRepository(self.db)

        # 2. Services
        self.user_manager = UserManager(database_file=self.DB_PATH)
        self.remote_worker = RemoteLogWorker(self.DB_PATH, os.getenv("DS_REMOTE_URL"), True)
        self.system_logger = SystemLogger(self.remote_worker, self.repo, self.vin)

        # 2b. GPS Worker (optional / non-fatal)
        self.gps_worker = None
        if self.gps_enabled:
            try:
                self.gps_worker = GPSWorker(
                    vehicle_id=self.gps_vehicle_id,
                    ws_url=self.gps_ws_url,
                    port=self.gps_port,
                    baud=self.gps_baud,
                )
                self.gps_worker.start()
                log.info("GPS worker initialized successfully")
            except Exception as e:
                log.warning("GPS worker failed to initialize: %s", e)

        # 3. Hardware
        self.camera = Camera(source='auto', resolution=(640, 480))
        if not self.camera.ready:
            raise RuntimeError("Camera failed to open")

    def _cleanup(self):
        log.info("Shutting down...")

        if hasattr(self, 'gps_worker') and self.gps_worker:
            self.gps_worker.close()

        if hasattr(self, 'remote_worker') and self.remote_worker:
            self.remote_worker.close()

        if hasattr(self, 'db') and self.db:
            self.db.close()

        if hasattr(self, 'camera') and self.camera:
            self.camera.release()

    cv2.destroyAllWindows()

    def _ensure_paths(self):
        Path("data").mkdir(exist_ok=True)
        Path("logs").mkdir(exist_ok=True)

    def _load_config(self):
        if Path(self.CONFIG_PATH).exists():
            with open(self.CONFIG_PATH) as f:
                return yaml.safe_load(f)
        return {}