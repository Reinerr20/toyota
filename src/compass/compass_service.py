import logging
import math
import time
from typing import Optional, Tuple

from src.compass.models import CompassState

log = logging.getLogger(__name__)


class CompassService:
    """
    Optional I2C compass reader for common M8N external compass chips.

    Supported:
    - QMC5883L at 0x0D
    - HMC5883L at 0x1E

    Detected but unsupported:
    - 0x0E, often IST8310 or another external compass variant
    """

    COMMON_ADDRESSES = {
        0x0D: "QMC5883L",
        0x1E: "HMC5883L",
        0x0E: "IST8310_OR_UNKNOWN",
    }

    def __init__(
        self,
        bus: int = 1,
        address: str = "auto",
        heading_offset_deg: float = 0.0,
        declination_deg: float = 0.0,
    ):
        self.bus_num = int(bus)
        self.address_arg = str(address or "auto").strip().lower()
        self.heading_offset_deg = float(heading_offset_deg)
        self.declination_deg = float(declination_deg)

        self._smbus_mod = None
        self._bus = None
        self.address: Optional[int] = None
        self.chip: Optional[str] = None
        self.connected = False
        self._unsupported_logged = False
        self._last_read_warn_ts = 0.0

    def connect(self) -> None:
        try:
            import smbus2  # type: ignore

            self._smbus_mod = smbus2
        except Exception as e:
            log.warning("Compass not detected: smbus2 unavailable (%s)", e)
            self.close()
            return

        try:
            self._bus = self._smbus_mod.SMBus(self.bus_num)
        except Exception as e:
            log.warning("Compass not detected: unable to open /dev/i2c-%s (%s)", self.bus_num, e)
            self.close()
            return

        addr = self._resolve_address()
        if addr is None:
            log.warning("Compass not detected")
            self.close()
            return

        self.address = addr
        self.chip = self.COMMON_ADDRESSES.get(addr, "UNKNOWN")

        if addr == 0x0E:
            log.warning("Compass detected at 0x0E but chip is unsupported (%s)", self.chip)
            self.close()
            return

        try:
            if self.chip == "QMC5883L":
                self._init_qmc5883l()
            elif self.chip == "HMC5883L":
                self._init_hmc5883l()
            else:
                log.warning("Compass detected at 0x%02X but chip is unsupported (%s)", addr, self.chip)
                self.close()
                return
        except Exception as e:
            log.warning("Compass not detected: initialization failed at 0x%02X (%s)", addr, e)
            self.close()
            return

        self.connected = True
        log.info("Compass service initialized successfully (%s at 0x%02X)", self.chip, self.address)

    def read(self) -> Optional[CompassState]:
        if not self.connected or self._bus is None or self.address is None or self.chip is None:
            return None

        try:
            if self.chip == "QMC5883L":
                x, y, z = self._read_qmc5883l()
            elif self.chip == "HMC5883L":
                x, y, z = self._read_hmc5883l()
            else:
                if not self._unsupported_logged:
                    log.warning("Compass detected but unsupported: %s", self.chip)
                    self._unsupported_logged = True
                return None

            heading_raw = self._normalize_deg(math.degrees(math.atan2(float(y), float(x))))
            heading = self._normalize_deg(
                heading_raw + self.heading_offset_deg + self.declination_deg
            )

            return CompassState(
                heading_deg=float(heading),
                heading_raw_deg=float(heading_raw),
                mag_x=float(x),
                mag_y=float(y),
                mag_z=float(z),
                source="compass",
                address=self._address_str(),
                chip=self.chip,
                compass_fix=True,
                ts_unix_ms=int(time.time() * 1000),
            )
        except Exception as e:
            now = time.time()
            if (now - self._last_read_warn_ts) >= 5.0:
                log.warning("Compass read failed: %s", e)
                self._last_read_warn_ts = now
            return None

    def close(self) -> None:
        if self._bus is not None:
            try:
                self._bus.close()
            except Exception:
                pass
        self._bus = None
        self.connected = False

    def _resolve_address(self) -> Optional[int]:
        if self.address_arg != "auto":
            try:
                return int(self.address_arg, 0)
            except Exception:
                log.warning("Compass not detected: invalid address %r", self.address_arg)
                return None

        for addr in self.COMMON_ADDRESSES:
            if self._probe(addr):
                return addr
        return None

    def _probe(self, addr: int) -> bool:
        if self._bus is None:
            return False
        try:
            self._bus.read_byte(addr)
            return True
        except Exception:
            return False

    def _init_qmc5883l(self) -> None:
        # Reset, then continuous measurement: OSR=512, RNG=8G, ODR=50Hz, continuous.
        self._bus.write_byte_data(self.address, 0x0B, 0x01)
        self._bus.write_byte_data(self.address, 0x09, 0x1D)
        time.sleep(0.01)

    def _init_hmc5883l(self) -> None:
        # 8-average 15Hz normal measurement, gain +/-1.3G, continuous mode.
        self._bus.write_byte_data(self.address, 0x00, 0x70)
        self._bus.write_byte_data(self.address, 0x01, 0x20)
        self._bus.write_byte_data(self.address, 0x02, 0x00)
        time.sleep(0.01)

    def _read_qmc5883l(self) -> Tuple[int, int, int]:
        data = self._bus.read_i2c_block_data(self.address, 0x00, 6)
        x = self._to_int16_le(data[0], data[1])
        y = self._to_int16_le(data[2], data[3])
        z = self._to_int16_le(data[4], data[5])
        return x, y, z

    def _read_hmc5883l(self) -> Tuple[int, int, int]:
        data = self._bus.read_i2c_block_data(self.address, 0x03, 6)
        x = self._to_int16_be(data[0], data[1])
        z = self._to_int16_be(data[2], data[3])
        y = self._to_int16_be(data[4], data[5])
        return x, y, z

    @staticmethod
    def _to_int16_le(lo: int, hi: int) -> int:
        val = (int(hi) << 8) | int(lo)
        return val - 65536 if val & 0x8000 else val

    @staticmethod
    def _to_int16_be(hi: int, lo: int) -> int:
        val = (int(hi) << 8) | int(lo)
        return val - 65536 if val & 0x8000 else val

    @staticmethod
    def _normalize_deg(value: float) -> float:
        return float(value % 360.0)

    def _address_str(self) -> Optional[str]:
        return f"0x{self.address:02X}" if self.address is not None else None
