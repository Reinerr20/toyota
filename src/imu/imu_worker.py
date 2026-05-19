import copy
import logging
import threading
import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Callable, Optional

from src.imu.imu_publisher import IMUPublisher
from src.imu.imu_service import IMUService
from src.imu.models import IMUState, PotholeCandidate

if TYPE_CHECKING:
    from src.gps.models import GPSState

log = logging.getLogger(__name__)


class IMUWorker:
    """Background IMU telemetry poller and low-rate optional HTTP publisher."""

    def __init__(
        self,
        imu_service: IMUService,
        publisher: Optional[IMUPublisher] = None,
        gps_provider: Optional[Callable[[], "GPSState"]] = None,
        sample_hz: float = 25.0,
        send_interval_sec: float = 1.0,
        publish_enabled: bool = False,
        pothole_detection_enabled: bool = False,
        min_speed_kmph: float = 5.0,
        accel_mag_threshold_g: float = 1.8,
        jerk_mag_threshold_gps: float = 8.0,
        event_cooldown_sec: float = 2.0,
    ):
        self.imu_service = imu_service
        self.publisher = publisher
        self.gps_provider = gps_provider
        self.sample_hz = max(float(sample_hz), 0.1)
        self.send_interval_sec = max(float(send_interval_sec), 0.1)
        self.publish_enabled = bool(publish_enabled)
        self.pothole_detection_enabled = bool(pothole_detection_enabled)
        self.min_speed_kmph = float(min_speed_kmph)
        self.accel_mag_threshold_g = float(accel_mag_threshold_g)
        self.jerk_mag_threshold_gps = float(jerk_mag_threshold_gps)
        self.event_cooldown_sec = float(event_cooldown_sec)

        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._latest_state: Optional[IMUState] = None
        self._latest_candidate = PotholeCandidate()
        self._last_send_ts = 0.0
        self._last_event_ts = 0.0
        self._last_payload_sent = False

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            daemon=True,
            name="IMUWorkerThread",
        )
        self._thread.start()
        log.info(
            "IMUWorker started (sample_hz=%s, send_interval=%s, publish_enabled=%s, pothole_detection_enabled=%s)",
            self.sample_hz,
            self.send_interval_sec,
            self.publish_enabled,
            self.pothole_detection_enabled,
        )

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        log.info("IMUWorker stopped")

    def close(self) -> None:
        self.stop()
        if self.publisher is not None:
            self.publisher.close()
        self.imu_service.close()

    def get_latest(self) -> Optional[IMUState]:
        with self._lock:
            return copy.deepcopy(self._latest_state)

    def get_latest_candidate(self) -> PotholeCandidate:
        with self._lock:
            return copy.deepcopy(self._latest_candidate)

    def get_last_payload_sent(self) -> bool:
        with self._lock:
            return bool(self._last_payload_sent)

    def build_payload(
        self,
        state: IMUState,
        gps_state: Optional["GPSState"] = None,
        candidate: Optional[PotholeCandidate] = None,
    ) -> dict:
        candidate = candidate or PotholeCandidate(ts_unix_ms=state.ts_unix_ms)
        ts_sec = (state.ts_unix_ms or int(time.time() * 1000)) / 1000

        raw_accel = (state.raw or {}).get("accel", {})

        return {
            "timestamp": datetime.fromtimestamp(ts_sec, tz=timezone.utc).isoformat(),
            "vehicle_id": self.publisher.vehicle_id if self.publisher else None,
            "gps": {
                "lat": getattr(gps_state, "lat", None),
                "lng": getattr(gps_state, "lng", None),
                "speed_kmh": getattr(gps_state, "speed_kmph", None),
                "satellites": getattr(gps_state, "satellites", None),
                "hdop": getattr(gps_state, "hdop", None),
            },
            "sensor": {
                "accel_raw": {
                    "x": raw_accel.get("x"),
                    "y": raw_accel.get("y"),
                    "z": raw_accel.get("z"),
                },
                "accel_ms2": {
                    "x": state.accel_x_ms2,
                    "y": state.accel_y_ms2,
                    "z": state.accel_z_ms2,
                },
                "gyro": {
                    "x": state.gyro_x_dps,
                    "y": state.gyro_y_dps,
                    "z": state.gyro_z_dps,
                },
                "linear_accel": {"x": None, "y": None, "z": None},
                "orient": {"heading": None, "roll": None, "pitch": None},
                "magneto": {"x": None, "y": None, "z": None},
                "gravity": {"x": None, "y": None, "z": None},
                "temp_c": state.temp_c,
            },
            "features": {
                "accel_mag_g": state.accel_mag_g,
                "accel_mag_ms2": state.accel_mag_ms2,
                "jerk_mag_gps": state.jerk_mag_gps,
            },
            "event": {
                "is_pothole_candidate": candidate.is_candidate,
                "severity": candidate.severity,
                "reason": candidate.reason,
            },
        }

    def _run(self) -> None:
        sleep_sec = 1.0 / self.sample_hz
        while not self._stop_event.is_set():
            loop_start = time.time()
            try:
                state = self.imu_service.read()
                if state is not None:
                    gps_state = self._get_gps_state()
                    candidate = self._evaluate_pothole_candidate(state, gps_state)

                    with self._lock:
                        self._latest_state = copy.deepcopy(state)
                        self._latest_candidate = copy.deepcopy(candidate)

                    now = time.time()
                    if (
                        self.publisher is not None
                        and self.publish_enabled
                        and (now - self._last_send_ts) >= self.send_interval_sec
                    ):
                        payload = self.build_payload(state, gps_state, candidate)
                        sent = self.publisher.send_payload(payload)
                        with self._lock:
                            self._last_payload_sent = sent
                        if sent:
                            self._last_send_ts = now
            except Exception as e:
                log.warning("IMUWorker loop error: %s", e, exc_info=True)

            elapsed = time.time() - loop_start
            time.sleep(max(0.0, sleep_sec - elapsed))

    def _get_gps_state(self) -> Optional["GPSState"]:
        if self.gps_provider is None:
            return None
        try:
            return self.gps_provider()
        except Exception as e:
            log.warning("IMU GPS provider failed: %s", e)
            return None

    def _evaluate_pothole_candidate(
        self,
        state: IMUState,
        gps_state: Optional["GPSState"],
    ) -> PotholeCandidate:
        speed = getattr(gps_state, "speed_kmph", None)
        now = time.time()
        candidate = PotholeCandidate(
            accel_mag_g=state.accel_mag_g,
            jerk_mag_gps=state.jerk_mag_gps,
            speed_kmph=speed,
            ts_unix_ms=state.ts_unix_ms,
        )

        if not self.pothole_detection_enabled:
            return candidate

        if speed is None:
            candidate.reason = "speed_unavailable"
            return candidate
        if speed < self.min_speed_kmph:
            candidate.reason = "below_min_speed"
            return candidate
        if state.accel_mag_g is None or state.jerk_mag_gps is None:
            candidate.reason = "features_unavailable"
            return candidate

        in_cooldown = (now - self._last_event_ts) < self.event_cooldown_sec
        candidate.cooldown_active = in_cooldown
        if in_cooldown:
            candidate.reason = "cooldown_active"
            return candidate

        accel_hit = state.accel_mag_g >= self.accel_mag_threshold_g
        jerk_hit = state.jerk_mag_gps >= self.jerk_mag_threshold_gps
        if not (accel_hit and jerk_hit):
            candidate.reason = "below_threshold"
            return candidate

        accel_ratio = state.accel_mag_g / self.accel_mag_threshold_g
        jerk_ratio = state.jerk_mag_gps / self.jerk_mag_threshold_gps
        strength = max(accel_ratio, jerk_ratio)
        if strength >= 2.0:
            severity = "High"
        elif strength >= 1.4:
            severity = "Medium"
        else:
            severity = "Low"

        candidate.is_candidate = True
        candidate.severity = severity
        candidate.reason = "accel_and_jerk_threshold"
        self._last_event_ts = now
        log.info("Pothole candidate detected: %s", candidate.to_dict())
        return candidate
