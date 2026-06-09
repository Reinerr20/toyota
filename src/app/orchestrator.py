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
from src.imu.imu_publisher import IMUPublisher
from src.imu.imu_service import IMUService
from src.imu.imu_worker import IMUWorker
from src.utils.config.runtime_config import PROJECT_ROOT, RuntimeConfig

log = logging.getLogger(__name__)


class DrowsinessSystem:
    CONFIG_PATH = "config/detector_config.yaml"
    RUNTIME_CONFIG_PATH = "config/runtime_config.yaml"

    def __init__(self):
        self.runtime = RuntimeConfig(self.RUNTIME_CONFIG_PATH)
        self._ensure_paths()
        self.config = self._load_config()
        sys_cfg = self.config.get("system", {})

        self.db_path = self.runtime.project_path(
            self.runtime.get_str("app.db_path", "data/cc.db", env="CC_DB_PATH")
        )
        self.log_dir = self.runtime.project_path(self.runtime.get_str("app.log_dir", "logs"))

        self.vin = self.runtime.get_str(
            "vehicle.vin",
            str(sys_cfg.get("vin", "VIN-0001")),
            env="DS_VIN",
        )
        self.dashboard_vehicle_id = self.runtime.get_str(
            "vehicle.dashboard_vehicle_id",
            "1210",
        )
        self.fps = float(sys_cfg.get("target_fps", 30.0))
        self.camera_source = self.runtime.get_str("camera.source", "auto", env="DS_CAMERA_SOURCE")
        self.camera_index = self.runtime.get_str("camera.index", "auto", env="DS_CAMERA_INDEX")
        self.identity_mode = self.runtime.get_str("identity.mode", "enrollment", env="DS_IDENTITY_MODE").strip().lower()
        if self.identity_mode not in {"operation", "enrollment"}:
            log.warning("[CONFIG] invalid identity mode %r; falling back to enrollment", self.identity_mode)
            self.identity_mode = "enrollment"
        os.environ.setdefault("DS_IDENTITY_MODE", self.identity_mode)

        self.remote_enabled = self.runtime.get_bool("remote.drowsiness_enabled", True, env="DS_REMOTE_ENABLED")
        self.remote_include_image = self.runtime.get_bool("remote.include_image", True, env="DS_REMOTE_INCLUDE_IMAGE")
        self.remote_image_max_width = self.runtime.get_int("remote.image_max_width", 480, env="DS_REMOTE_IMAGE_MAX_WIDTH")
        self.remote_image_jpeg_quality = self.runtime.get_int("remote.image_jpeg_quality", 60, env="DS_REMOTE_IMAGE_JPEG_QUALITY")
        self.remote_retry_event_only_on_413 = self.runtime.get_bool("remote.retry_event_only_on_413", True, env="DS_REMOTE_RETRY_EVENT_ONLY_ON_413")
        self.evidence_retry_enabled = self.runtime.get_bool("remote.evidence_retry_enabled", True, env="DS_EVIDENCE_RETRY_ENABLED")
        self.evidence_retry_interval_sec = self.runtime.get_float("remote.evidence_retry_interval_sec", 60.0, env="DS_EVIDENCE_RETRY_INTERVAL_SEC")
        self.evidence_retry_backoff_sec = self.runtime.get_float("remote.evidence_retry_backoff_sec", 300.0, env="DS_EVIDENCE_RETRY_BACKOFF_SEC")
        self.evidence_retry_max_attempts = self.runtime.get_int("remote.evidence_retry_max_attempts", 10, env="DS_EVIDENCE_RETRY_MAX_ATTEMPTS")

        # GPS core config
        self.gps_enabled = self.runtime.get_bool("gps.enabled", True, env="DS_GPS_ENABLED")
        self.gps_port = self.runtime.get_str("gps.port", "/dev/ttyAMA0", env="DS_GPS_PORT")
        self.gps_baud = self.runtime.get_int("gps.baud", 9600, env="DS_GPS_BAUD")
        self.gps_poll_interval_sec = float(
            os.getenv(
                "DS_GPS_POLL_INTERVAL_SEC",
                sys_cfg.get("gps_poll_interval_sec", 0.2),
            )
        )

        # GPS live dashboard publish config
        self.gps_publish_enabled = self.runtime.get_bool("gps.publish_enabled", True, env="DS_GPS_PUBLISH_ENABLED")
        self.gps_vehicle_id = self.runtime.get_str("gps.vehicle_id", self.dashboard_vehicle_id, env="DS_GPS_VEHICLE_ID")
        self.gps_ws_url = self.runtime.get_str(
            "gps.ws_url",
            f"ws://203.100.57.59:3300/?vehicle_id={self.gps_vehicle_id}&device=GPS",
            env="DS_GPS_WS_URL",
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
        self.compass_enabled = self.runtime.get_bool("compass.enabled", True, env="DS_COMPASS_ENABLED")
        self.compass_bus = self.runtime.get_int("compass.bus", 1, env="DS_COMPASS_BUS")
        self.compass_address = self.runtime.get_str("compass.address", "auto", env="DS_COMPASS_ADDRESS")
        self.compass_heading_offset_deg = self.runtime.get_float("compass.heading_offset_deg", 0.0, env="DS_COMPASS_HEADING_OFFSET_DEG")
        self.compass_declination_deg = self.runtime.get_float("compass.declination_deg", 0.0, env="DS_COMPASS_DECLINATION_DEG")
        self.compass_publish_enabled = self.runtime.get_bool("compass.publish_enabled", True, env="DS_COMPASS_PUBLISH_ENABLED")

        # Optional IMU/pothole telemetry config
        self.imu_enabled = self.runtime.get_bool("imu.enabled", True, env="DS_IMU_ENABLED")
        self.imu_bus = self.runtime.get_int("imu.bus", 1, env="DS_IMU_BUS")
        self.imu_address = self.runtime.get_str("imu.address", "auto", env="DS_IMU_ADDRESS")
        self.imu_sample_hz = self.runtime.get_float("imu.sample_hz", 25.0, env="DS_IMU_SAMPLE_HZ")
        self.imu_publish_enabled = self.runtime.get_bool("imu.publish_enabled", True, env="DS_IMU_PUBLISH_ENABLED")
        self.imu_post_url = self.runtime.get_str(
            "imu.post_url",
            "http://203.100.57.59:3000/api/v1/pothole/add",
            env="DS_IMU_POST_URL",
        )
        self.imu_vehicle_id = self.runtime.get_str("imu.vehicle_id", self.dashboard_vehicle_id, env="DS_IMU_VEHICLE_ID")
        self.imu_send_interval_sec = self.runtime.get_float("imu.send_interval_sec", 1.0, env="DS_IMU_SEND_INTERVAL_SEC")
        self.imu_timeout_sec = float(
            os.getenv("DS_IMU_TIMEOUT_SEC", sys_cfg.get("imu_timeout_sec", 3.0))
        )
        self.imu_pothole_detection_enabled = self.runtime.get_bool(
            "imu.pothole_detection_enabled",
            False,
            env="DS_IMU_POTHOLE_DETECTION_ENABLED",
        )
        self.imu_compat_payload = self.runtime.get_bool("imu.compat_payload", True, env="DS_IMU_COMPAT_PAYLOAD")
        self.imu_min_speed_kmph = float(
            os.getenv(
                "DS_IMU_MIN_SPEED_KMPH",
                sys_cfg.get("imu_min_speed_kmph", 5.0),
            )
        )
        self.imu_accel_mag_threshold_g = float(
            os.getenv(
                "DS_IMU_ACCEL_MAG_THRESHOLD_G",
                sys_cfg.get("imu_accel_mag_threshold_g", 1.8),
            )
        )
        self.imu_jerk_mag_threshold_gps = float(
            os.getenv(
                "DS_IMU_JERK_MAG_THRESHOLD_GPS",
                sys_cfg.get("imu_jerk_mag_threshold_gps", 8.0),
            )
        )
        self.imu_event_cooldown_sec = float(
            os.getenv(
                "DS_IMU_EVENT_COOLDOWN_SEC",
                sys_cfg.get("imu_event_cooldown_sec", 2.0),
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
        self.imu_publisher = None
        self.imu_service = None
        self.imu_worker = None
        self.camera = None

    def run(self):
        try:
            self._init_resources()
            self._print_runtime_summary()
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
        self.db = UnifiedDatabase(self.db_path)
        self.repo = UnifiedRepository(self.db)

        # 2. Services
        self.user_manager = UserManager(database_file=self.db_path)
        self.remote_worker = RemoteLogWorker(
            self.db_path,
            os.getenv("DS_REMOTE_URL"),
            self.remote_enabled,
            include_image=self.remote_include_image,
            image_max_width=self.remote_image_max_width,
            image_jpeg_quality=self.remote_image_jpeg_quality,
            retry_event_only_on_413=self.remote_retry_event_only_on_413,
            evidence_retry_enabled=self.evidence_retry_enabled,
            evidence_retry_interval_sec=self.evidence_retry_interval_sec,
            evidence_retry_backoff_sec=self.evidence_retry_backoff_sec,
            evidence_retry_max_attempts=self.evidence_retry_max_attempts,
        )
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
                log.warning("[GPS] enabled but unavailable: publisher init failed: %s", e, exc_info=True)
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
                    log.warning("[COMPASS] enabled but unavailable: compass not detected")
                    self.compass_service = None
            except Exception as e:
                log.warning("[COMPASS] enabled but unavailable: %s", e, exc_info=True)
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
                log.warning("[GPS] enabled but unavailable: %s", e, exc_info=True)
                self.gps_worker = None

        # 6. IMU worker (optional / non-fatal)
        log.info(
            "IMU enabled=%s publish_enabled=%s pothole_detection_enabled=%s",
            self.imu_enabled,
            self.imu_publish_enabled,
            self.imu_pothole_detection_enabled,
        )
        if self.imu_enabled:
            try:
                self.imu_service = IMUService(
                    bus=self.imu_bus,
                    address=self.imu_address,
                )
                self.imu_service.connect()
                if self.imu_service.is_connected():
                    log.info(
                        "IMU detected (%s at %s)",
                        self.imu_service.chip,
                        self.imu_service._address_str(),
                    )
                    if self.imu_publish_enabled:
                        self.imu_publisher = IMUPublisher(
                            post_url=self.imu_post_url,
                            vehicle_id=self.imu_vehicle_id,
                            timeout_sec=self.imu_timeout_sec,
                            enabled=True,
                        )

                    self.imu_worker = IMUWorker(
                        imu_service=self.imu_service,
                        publisher=self.imu_publisher,
                        gps_provider=self.gps_worker.get_latest if self.gps_worker else None,
                        sample_hz=self.imu_sample_hz,
                        send_interval_sec=self.imu_send_interval_sec,
                        publish_enabled=self.imu_publish_enabled,
                        pothole_detection_enabled=self.imu_pothole_detection_enabled,
                        min_speed_kmph=self.imu_min_speed_kmph,
                        accel_mag_threshold_g=self.imu_accel_mag_threshold_g,
                        jerk_mag_threshold_gps=self.imu_jerk_mag_threshold_gps,
                        event_cooldown_sec=self.imu_event_cooldown_sec,
                        compat_payload=self.imu_compat_payload,
                    )
                    self.imu_worker.start()
                else:
                    log.warning("[IMU] enabled but unavailable: IMU not detected")
                    self.imu_service = None
            except Exception as e:
                log.warning("[IMU] enabled but unavailable: %s", e, exc_info=True)
                if self.imu_publisher:
                    self.imu_publisher.close()
                if self.imu_service:
                    self.imu_service.close()
                self.imu_publisher = None
                self.imu_service = None
                self.imu_worker = None

        # 7. Hardware
        self.camera = Camera(source=self.camera_source, index=self.camera_index, resolution=(640, 480))
        if not self.camera.ready:
            raise RuntimeError("Camera failed to open")

    def _cleanup(self):
        log.info("Shutting down...")

        if self.imu_worker:
            self.imu_worker.close()
            self.imu_worker = None
            self.imu_publisher = None
            self.imu_service = None
        else:
            if self.imu_publisher:
                self.imu_publisher.close()
            if self.imu_service:
                self.imu_service.close()

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
        data_dir = Path(self.runtime.project_path(self.runtime.get_str("app.db_path", "data/cc.db"))).parent
        log_dir = Path(self.runtime.project_path(self.runtime.get_str("app.log_dir", "logs")))
        data_dir.mkdir(parents=True, exist_ok=True)
        log_dir.mkdir(parents=True, exist_ok=True)

    def _load_config(self):
        path = PROJECT_ROOT / self.CONFIG_PATH
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        return {}

    def _display_path(self, path: str) -> str:
        try:
            return str(Path(path).resolve().relative_to(PROJECT_ROOT))
        except ValueError:
            return str(path)

    def _print_runtime_summary(self):
        camera_detected = getattr(self.camera, "device_index", None)
        camera_index_summary = self.camera_index
        if camera_detected is not None:
            camera_index_summary = f"{self.camera_index} / detected={camera_detected}"

        log.info("[CONFIG] runtime config: %s", self.runtime.display_path())
        log.info("[CONFIG] DB path: %s", self._display_path(self.db_path))
        log.info("[CONFIG] VIN: %s", self.vin)
        log.info("[CONFIG] dashboard vehicle_id: %s", self.dashboard_vehicle_id)
        log.info("[CONFIG] camera source: %s", self.camera_source)
        log.info("[CONFIG] camera index: %s", camera_index_summary)
        log.info("[CONFIG] identity mode: %s", self.identity_mode)
        log.info("[CONFIG] remote drowsiness enabled: %s", self.remote_enabled)
        log.info("[CONFIG] remote include image: %s", self.remote_include_image)
        log.info("[CONFIG] remote image max width: %s", self.remote_image_max_width)
        log.info("[CONFIG] remote image JPEG quality: %s", self.remote_image_jpeg_quality)
        log.info("[CONFIG] evidence retry enabled: %s", self.evidence_retry_enabled)
        log.info(
            "[CONFIG] GPS enabled: %s publish=%s port=%s baud=%s",
            self.gps_enabled,
            self.gps_publish_enabled,
            self.gps_port,
            self.gps_baud,
        )
        log.info("[CONFIG] GPS WS URL: %s", self.gps_ws_url)
        log.info(
            "[CONFIG] compass enabled: %s bus=%s address=%s",
            self.compass_enabled,
            self.compass_bus,
            self.compass_address,
        )
        log.info(
            "[CONFIG] IMU enabled: %s bus=%s address=%s",
            self.imu_enabled,
            self.imu_bus,
            self.imu_address,
        )
        log.info("[CONFIG] pothole detection enabled: %s", self.imu_pothole_detection_enabled)

    @staticmethod
    def _to_bool(value):
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "on"}
