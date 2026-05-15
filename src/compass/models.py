from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional


@dataclass
class CompassState:
    heading_deg: Optional[float] = None
    heading_raw_deg: Optional[float] = None
    mag_x: Optional[float] = None
    mag_y: Optional[float] = None
    mag_z: Optional[float] = None
    source: str = "compass"
    address: Optional[str] = None
    chip: Optional[str] = None
    compass_fix: bool = False
    ts_unix_ms: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
