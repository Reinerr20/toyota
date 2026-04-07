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

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)