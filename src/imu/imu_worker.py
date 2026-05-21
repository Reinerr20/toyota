import copy
import json
import logging
import threading
import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Callable, Optional, Union

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
        compat_payload: bool = False,
        mock_gps: Optional[dict] = None,
        print_payload: bool = False,
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
        self.compat_payload = bool(compat_payload)
        self.mock_gps = copy.deepcopy(mock_gps) if mock_gps else None
        self.print_payload = bool(print_payload)

        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._latest_state: Optional[IMUState] = None
        self._latest_candidate = PotholeCandidate()
        self._last_send_ts = 0.0
        self._last_event_ts = 0.0
        self._last_payload_sent = False
        self._last_skip_log_ts = 0.0
        self._baseline_started_ts: Optional[float] = None
        self._baseline_samples = 0
        self._baseline_sum_x = 0.0
        self._baseline_sum_y = 0.0
        self._baseline_sum_z = 0.0
        self._accel_baseline_ms2: Optional[tuple] = None

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
            "IMUWorker started (sample_hz=%s, send_interval=%s, publish_enabled=%s, pothole_detection_enabled=%s, compat_payload=%s)",
            self.sample_hz,
            self.send_interval_sec,
            self.publish_enabled,
            self.pothole_detection_enabled,
            self.compat_payload,
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
        gps_state: Optional[Union["GPSState", dict]] = None,
        candidate: Optional[PotholeCandidate] = None,
    ) -> dict:
        if self.compat_payload:
            return self.build_compat_payload(state, gps_state)

        candidate = candidate or PotholeCandidate(ts_unix_ms=state.ts_unix_ms)
        ts_sec = (state.ts_unix_ms or int(time.time() * 1000)) / 1000

        raw_accel = (state.raw or {}).get("accel", {})

        return {
            "timestamp": datetime.fromtimestamp(ts_sec, tz=timezone.utc).isoformat(),
            "vehicle_id": self.publisher.vehicle_id if self.publisher else None,
            "gps": {
                "lat": self._gps_value(gps_state, "lat", None),
                "lng": self._gps_value(gps_state, "lng", None),
                "speed_kmh": self._gps_value(gps_state, "speed_kmph", None),
                "satellites": self._gps_value(gps_state, "satellites", None),
                "hdop": self._gps_value(gps_state, "hdop", None),
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

    def build_compat_payload(
        self,
        state: IMUState,
        gps_state: Optional[Union["GPSState", dict]] = None,
    ) -> dict:
        ts_sec = (state.ts_unix_ms or int(time.time() * 1000)) / 1000
        linear_x, linear_y, linear_z = self._linear_accel_ms2(state)

        return {
            "timestamp": datetime.fromtimestamp(ts_sec).strftime("%Y-%m-%d %H:%M:%S"),
            "gps": {
                "lat": self._number(self._gps_value(gps_state, "lat", 0.0)),
                "lng": self._number(self._gps_value(gps_state, "lng", 0.0)),
                "speed_kmh": self._number(self._gps_value(gps_state, "speed_kmph", 0.0)),
                "satellites": int(self._number(self._gps_value(gps_state, "satellites", 0))),
            },
            "sensor": {
                "orient": {"heading": 0.0, "roll": 0.0, "pitch": 0.0},
                "linear_accel": {
                    "x": linear_x,
                    "y": linear_y,
                    "z": linear_z,
                },
                "gyro": {
                    "x": self._number(state.gyro_x_dps),
                    "y": self._number(state.gyro_y_dps),
                    "z": self._number(state.gyro_z_dps),
                },
                "magneto": {"x": 0.0, "y": 0.0, "z": 0.0},
                "accel_raw": {
                    "x": self._number(state.accel_x_g),
                    "y": self._number(state.accel_y_g),
                    "z": self._number(state.accel_z_g),
                },
                "gravity": {"x": 0.0, "y": 0.0, "z": 9.80665},
                "temp_c": self._number(state.temp_c),
            },
        }

    def _run(self) -> None:
        sleep_sec = 1.0 / self.sample_hz
        while not self._stop_event.is_set():
            loop_start = time.time()
            try:
                state = self.imu_service.read()
                if state is not None:
                    self._update_accel_baseline(state)
                    gps_state = self._effective_gps_state(self._get_gps_state())
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
                        if self.compat_payload and not self._has_valid_lat_lng(gps_state):
                            self._log_skip_post()
                            with self._lock:
                                self._last_payload_sent = False
                            self._last_send_ts = now
                            continue

                        payload = self.build_payload(state, gps_state, candidate)
                        if self.print_payload:
                            print(json.dumps(payload, separators=(",", ":")), flush=True)
                        sent = self.publisher.send_payload(payload)
                        with self._lock:
                            self._last_payload_sent = sent
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

    def _effective_gps_state(
        self,
        gps_state: Optional[Union["GPSState", dict]],
    ) -> Optional[Union["GPSState", dict]]:
        if self._has_valid_lat_lng(gps_state):
            return gps_state
        if self._has_valid_lat_lng(self.mock_gps):
            return self.mock_gps
        return gps_state

    def _evaluate_pothole_candidate(
        self,
        state: IMUState,
        gps_state: Optional[Union["GPSState", dict]],
    ) -> PotholeCandidate:
        speed = self._gps_value(gps_state, "speed_kmph", None)
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
        try:
            speed = float(speed)
        except Exception:
            candidate.reason = "speed_unavailable"
            return candidate
        candidate.speed_kmph = speed
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

    def _update_accel_baseline(self, state: IMUState) -> None:
        if self._accel_baseline_ms2 is not None:
            return
        if (
            state.accel_x_ms2 is None
            or state.accel_y_ms2 is None
            or state.accel_z_ms2 is None
        ):
            return

        now = time.time()
        if self._baseline_started_ts is None:
            self._baseline_started_ts = now

        self._baseline_samples += 1
        self._baseline_sum_x += float(state.accel_x_ms2)
        self._baseline_sum_y += float(state.accel_y_ms2)
        self._baseline_sum_z += float(state.accel_z_ms2)

        if (now - self._baseline_started_ts) >= 1.0 or self._baseline_samples >= 25:
            self._accel_baseline_ms2 = (
                self._baseline_sum_x / self._baseline_samples,
                self._baseline_sum_y / self._baseline_samples,
                self._baseline_sum_z / self._baseline_samples,
            )
            log.info(
                "IMU linear acceleration baseline set: x=%.3f y=%.3f z=%.3f",
                self._accel_baseline_ms2[0],
                self._accel_baseline_ms2[1],
                self._accel_baseline_ms2[2],
            )

    def _linear_accel_ms2(self, state: IMUState) -> tuple:
        if self._accel_baseline_ms2 is None:
            return 0.0, 0.0, 0.0
        return (
            self._number(state.accel_x_ms2) - self._accel_baseline_ms2[0],
            self._number(state.accel_y_ms2) - self._accel_baseline_ms2[1],
            self._number(state.accel_z_ms2) - self._accel_baseline_ms2[2],
        )

    @staticmethod
    def _gps_value(gps_state: Optional[Union["GPSState", dict]], key: str, default):
        if gps_state is None:
            return default
        if isinstance(gps_state, dict):
            return gps_state.get(key, default)
        return getattr(gps_state, key, default)

    @staticmethod
    def _number(value, default: float = 0.0) -> float:
        if value is None:
            return float(default)
        return float(value)

    def _has_valid_lat_lng(self, gps_state: Optional[Union["GPSState", dict]]) -> bool:
        lat = self._gps_value(gps_state, "lat", None)
        lng = self._gps_value(gps_state, "lng", None)
        try:
            return lat is not None and lng is not None and float(lat) != 0.0 and float(lng) != 0.0
        except Exception:
            return False

    def _log_skip_post(self) -> None:
        now = time.time()
        if (now - self._last_skip_log_ts) >= self.send_interval_sec:
            log.warning("Skipping POST: GPS lat/lng required by backend.")
            print("Skipping POST: GPS lat/lng required by backend.", flush=True)
            self._last_skip_log_ts = now
