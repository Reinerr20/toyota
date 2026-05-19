from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional


@dataclass
class IMUState:
    ts_unix_ms: Optional[int] = None
    chip: Optional[str] = None
    address: Optional[str] = None
    bus: int = 1
    accel_x_g: Optional[float] = None
    accel_y_g: Optional[float] = None
    accel_z_g: Optional[float] = None
    accel_x_ms2: Optional[float] = None
    accel_y_ms2: Optional[float] = None
    accel_z_ms2: Optional[float] = None
    gyro_x_dps: Optional[float] = None
    gyro_y_dps: Optional[float] = None
    gyro_z_dps: Optional[float] = None
    temp_c: Optional[float] = None
    accel_mag_g: Optional[float] = None
    accel_mag_ms2: Optional[float] = None
    jerk_x_gps: Optional[float] = None
    jerk_y_gps: Optional[float] = None
    jerk_z_gps: Optional[float] = None
    jerk_mag_gps: Optional[float] = None
    sample_dt_sec: Optional[float] = None
    imu_ok: bool = False
    raw: Optional[dict] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PotholeCandidate:
    is_candidate: bool = False
    severity: str = "None"
    reason: Optional[str] = None
    accel_mag_g: Optional[float] = None
    jerk_mag_gps: Optional[float] = None
    speed_kmph: Optional[float] = None
    cooldown_active: bool = False
    ts_unix_ms: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

