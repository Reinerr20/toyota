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
from src.gps.gps_publisher import GPSPublisher
from src.compass.compass_service import CompassService

log = logging.getLogger(__name__)


class DrowsinessSystem:
    CONFIG_PATH = "config/detector_config.yaml"
    DB_PATH = os.getenv("CC_DB_PATH", os.path.join("data", "cc.db"))

    def __init__(self):
        self._ensure_paths()
        self.config = self._load_config()
        sys_cfg = self.config.get("system", {})

        self.vin = sys_cfg.get("vin", os.getenv("DS_VIN", "VIN-0001"))
        self.fps = float(sys_cfg.get("target_fps", 30.0))

        # GPS core config
        self.gps_enabled = self._to_bool(
            os.getenv("DS_GPS_ENABLED", sys_cfg.get("gps_enabled", False))
        )
        self.gps_port = os.getenv(
            "DS_GPS_PORT",
            sys_cfg.get("gps_port", "/dev/ttyAMA0"),
        )
        self.gps_baud = int(
            os.getenv("DS_GPS_BAUD", sys_cfg.get("gps_baud", 9600))
        )
        self.gps_poll_interval_sec = float(
            os.getenv(
                "DS_GPS_POLL_INTERVAL_SEC",
                sys_cfg.get("gps_poll_interval_sec", 0.2),
            )
        )

        # GPS live dashboard publish config
        self.gps_publish_enabled = self._to_bool(
            os.getenv("DS_GPS_PUBLISH_ENABLED", sys_cfg.get("gps_publish_enabled", False))
        )
        self.gps_vehicle_id = str(
            os.getenv("DS_GPS_VEHICLE_ID", sys_cfg.get("gps_vehicle_id", "1210"))
        )
        self.gps_ws_url = os.getenv(
            "DS_GPS_WS_URL",
            sys_cfg.get(
                "gps_ws_url",
                f"ws://203.100.57.59:3300/?vehicle_id={self.gps_vehicle_id}&device=GPS",
            ),
        )
        self.gps_send_interval_sec = float(
            os.getenv(
                "DS_GPS_SEND_INTERVAL_SEC",
                sys_cfg.get("gps_send_interval_sec", 2.0),
            )
        )
        self.gps_ws_reconnect_interval_sec = float(
            os.getenv(
                "DS_GPS_WS_RECONNECT_INTERVAL_SEC",
                sys_cfg.get("gps_ws_reconnect_interval_sec", 3.0),
            )
        )

        # Optional compass config
        self.compass_enabled = self._to_bool(
            os.getenv("DS_COMPASS_ENABLED", sys_cfg.get("compass_enabled", False))
        )
        self.compass_bus = int(
            os.getenv("DS_COMPASS_BUS", sys_cfg.get("compass_bus", 1))
        )
        self.compass_address = str(
            os.getenv("DS_COMPASS_ADDRESS", sys_cfg.get("compass_address", "auto"))
        )
        self.compass_heading_offset_deg = float(
            os.getenv(
                "DS_COMPASS_HEADING_OFFSET_DEG",
                sys_cfg.get("compass_heading_offset_deg", 0.0),
            )
        )
        self.compass_declination_deg = float(
            os.getenv(
                "DS_COMPASS_DECLINATION_DEG",
                sys_cfg.get("compass_declination_deg", 0.0),
            )
        )
        self.compass_publish_enabled = self._to_bool(
            os.getenv(
                "DS_COMPASS_PUBLISH_ENABLED",
                sys_cfg.get("compass_publish_enabled", True),
            )
        )

        self.db = None
        self.repo = None
        self.user_manager = None
        self.remote_worker = None
        self.system_logger = None
        self.gps_publisher = None
        self.gps_worker = None
        self.compass_service = None
        self.camera = None

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

        # 3. GPS publisher (optional / non-fatal)
        if self.gps_enabled and self.gps_publish_enabled:
            try:
                self.gps_publisher = GPSPublisher(
                    vehicle_id=self.gps_vehicle_id,
                    ws_url=self.gps_ws_url,
                    reconnect_interval_sec=self.gps_ws_reconnect_interval_sec,
                )
                log.info("GPS publisher initialized successfully")
            except Exception as e:
                log.warning("GPS publisher failed to initialize: %s", e, exc_info=True)
                self.gps_publisher = None

        # 4. Compass service (optional / non-fatal)
        if self.compass_enabled:
            try:
                self.compass_service = CompassService(
                    bus=self.compass_bus,
                    address=self.compass_address,
                    heading_offset_deg=self.compass_heading_offset_deg,
                    declination_deg=self.compass_declination_deg,
                )
                self.compass_service.connect()
                if getattr(self.compass_service, "connected", False):
                    log.info("Compass service initialized successfully")
                else:
                    self.compass_service = None
            except Exception as e:
                log.warning("Compass service failed to initialize: %s", e, exc_info=True)
                self.compass_service = None

        # 5. GPS worker (optional / non-fatal)
        if self.gps_enabled:
            try:
                self.gps_worker = GPSWorker(
                    port=self.gps_port,
                    baud=self.gps_baud,
                    poll_interval_sec=self.gps_poll_interval_sec,
                    publisher=self.gps_publisher,
                    send_interval_sec=self.gps_send_interval_sec,
                    compass_service=self.compass_service,
                    compass_publish_enabled=self.compass_publish_enabled,
                )
                self.gps_worker.start()
                log.info("GPS worker initialized successfully")
            except Exception as e:
                log.warning("GPS worker failed to initialize: %s", e, exc_info=True)
                self.gps_worker = None

        # 6. Hardware
        self.camera = Camera(source="auto", resolution=(640, 480))
        if not self.camera.ready:
            raise RuntimeError("Camera failed to open")

    def _cleanup(self):
        log.info("Shutting down...")

        if self.gps_worker:
            self.gps_worker.close()

        if self.gps_publisher:
            self.gps_publisher.close()

        if self.compass_service:
            self.compass_service.close()

        if self.remote_worker:
            self.remote_worker.close()

        if self.db:
            self.db.close()

        if self.camera:
            self.camera.release()

        cv2.destroyAllWindows()

    def _ensure_paths(self):
        Path("data").mkdir(exist_ok=True)
        Path("logs").mkdir(exist_ok=True)

    def _load_config(self):
        if Path(self.CONFIG_PATH).exists():
            with open(self.CONFIG_PATH, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        return {}

    @staticmethod
    def _to_bool(value):
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "on"}
