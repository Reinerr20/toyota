from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any


@dataclass
class GPSState:
    lat: Optional[float] = None
    lng: Optional[float] = None
    speed_kmph: Optional[float] = None
    satellites: Optional[int] = None
    hdop: Optional[float] = None
    course_deg: Optional[float] = None
    altitude_m: Optional[float] = None
    gps_fix: bool = False
    last_sentence: Optional[str] = None
    source_port: Optional[str] = None
    raw_line: Optional[str] = None

    # NEW: timing + ordering metadata
    gps_read_ts_unix_ms: Optional[int] = None  # when GPS sentence/state was parsed
    ts_unix_ms: Optional[int] = None           # when payload was sent/published
    seq: Optional[int] = None                  # monotonically increasing per app run

    # Optional compass enrichment
    heading_deg: Optional[float] = None
    heading_source: Optional[str] = None
    compass_fix: bool = False
    mag_x: Optional[float] = None
    mag_y: Optional[float] = None
    mag_z: Optional[float] = None
    compass_chip: Optional[str] = None
    compass_address: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
