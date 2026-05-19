import logging
import math
import time
from typing import Optional, Tuple

from src.imu.models import IMUState

log = logging.getLogger(__name__)


class IMUService:
    """
    Optional I2C IMU reader.

    First implementation supports raw MPU-series acquisition at 0x68/0x69.
    BNO055-like addresses are detected and logged, but not read yet.
    """

    MPU_ADDRESSES = (0x68, 0x69)
    BNO055_ADDRESSES = (0x28, 0x29)
    AUX_ONLY_ADDRESSES = (0x76, 0x77)
    AUTO_ADDRESSES = MPU_ADDRESSES + BNO055_ADDRESSES + AUX_ONLY_ADDRESSES

    GRAVITY_MS2 = 9.80665
    MPU_ACCEL_SCALE_LSB_PER_G = 16384.0
    MPU_GYRO_SCALE_LSB_PER_DPS = 131.0

    def __init__(self, bus: int = 1, address: str = "auto"):
        self.bus_num = int(bus)
        self.address_arg = str(address or "auto").strip().lower()

        self._smbus_mod = None
        self._bus = None
        self.address: Optional[int] = None
        self.chip: Optional[str] = None
        self.connected = False
        self._last_read_warn_ts = 0.0
        self._last_sample_ts = None
        self._last_accel_g: Optional[Tuple[float, float, float]] = None

    def connect(self) -> None:
        try:
            import smbus2  # type: ignore

            self._smbus_mod = smbus2
        except Exception as e:
            log.warning("IMU not detected: smbus2 unavailable (%s)", e)
            self.close()
            return

        try:
            self._bus = self._smbus_mod.SMBus(self.bus_num)
        except Exception as e:
            log.warning("IMU not detected: unable to open /dev/i2c-%s (%s)", self.bus_num, e)
            self.close()
            return

        addr = self._resolve_address()
        if addr is None:
            log.warning("IMU not detected")
            self.close()
            return

        self.address = addr

        if addr in self.MPU_ADDRESSES:
            if not self._init_mpu_series():
                self.close()
                return
        elif addr in self.BNO055_ADDRESSES:
            self.chip = "BNO055_OR_COMPATIBLE"
            log.warning(
                "BNO055-like IMU detected at 0x%02X, but BNO055 reads are not implemented",
                addr,
            )
            self.close()
            return
        elif addr in self.AUX_ONLY_ADDRESSES:
            self.chip = "BMP280_BME280_AUX_ONLY"
            log.warning(
                "Auxiliary sensor detected at 0x%02X (%s), but no supported IMU was found",
                addr,
                self.chip,
            )
            self.close()
            return
        else:
            self.chip = "UNKNOWN"
            log.warning("IMU detected at 0x%02X but chip is unsupported", addr)
            self.close()
            return

        self.connected = True
        log.info("IMU service initialized successfully (%s at 0x%02X)", self.chip, self.address)

    def read(self) -> Optional[IMUState]:
        if not self.connected or self._bus is None or self.address is None:
            return None

        try:
            if self.chip and self.chip.startswith("MPU"):
                return self._read_mpu_series()

            self._log_read_warning("IMU read unsupported for chip=%s", self.chip)
            return None
        except Exception as e:
            self._log_read_warning("IMU read failed: %s", e)
            return None

    def close(self) -> None:
        if self._bus is not None:
            try:
                self._bus.close()
            except Exception:
                pass
        self._bus = None
        self.connected = False

    def is_connected(self) -> bool:
        return bool(self.connected)

    def _resolve_address(self) -> Optional[int]:
        if self.address_arg != "auto":
            try:
                addr = int(self.address_arg, 0)
            except Exception:
                log.warning("IMU not detected: invalid address %r", self.address_arg)
                return None
            return addr if self._probe(addr) else None

        for addr in self.AUTO_ADDRESSES:
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

    def _init_mpu_series(self) -> bool:
        if self._bus is None or self.address is None:
            return False

        try:
            who_am_i = self._bus.read_byte_data(self.address, 0x75)
            self.chip = self._mpu_chip_name(who_am_i)
            self._bus.write_byte_data(self.address, 0x6B, 0x00)
            time.sleep(0.05)
            return True
        except Exception as e:
            log.warning("IMU not detected: MPU initialization failed at 0x%02X (%s)", self.address, e)
            return False

    def _read_mpu_series(self) -> IMUState:
        now = time.time()
        ts_unix_ms = int(now * 1000)
        data = self._bus.read_i2c_block_data(self.address, 0x3B, 14)

        accel_x_raw = self._to_int16_be(data[0], data[1])
        accel_y_raw = self._to_int16_be(data[2], data[3])
        accel_z_raw = self._to_int16_be(data[4], data[5])
        temp_raw = self._to_int16_be(data[6], data[7])
        gyro_x_raw = self._to_int16_be(data[8], data[9])
        gyro_y_raw = self._to_int16_be(data[10], data[11])
        gyro_z_raw = self._to_int16_be(data[12], data[13])

        accel_x_g = accel_x_raw / self.MPU_ACCEL_SCALE_LSB_PER_G
        accel_y_g = accel_y_raw / self.MPU_ACCEL_SCALE_LSB_PER_G
        accel_z_g = accel_z_raw / self.MPU_ACCEL_SCALE_LSB_PER_G
        accel_x_ms2 = accel_x_g * self.GRAVITY_MS2
        accel_y_ms2 = accel_y_g * self.GRAVITY_MS2
        accel_z_ms2 = accel_z_g * self.GRAVITY_MS2
        gyro_x_dps = gyro_x_raw / self.MPU_GYRO_SCALE_LSB_PER_DPS
        gyro_y_dps = gyro_y_raw / self.MPU_GYRO_SCALE_LSB_PER_DPS
        gyro_z_dps = gyro_z_raw / self.MPU_GYRO_SCALE_LSB_PER_DPS
        temp_c = temp_raw / 340.0 + 36.53

        accel_mag_g = math.sqrt(accel_x_g**2 + accel_y_g**2 + accel_z_g**2)
        accel_mag_ms2 = accel_mag_g * self.GRAVITY_MS2

        dt = None
        jerk_x = None
        jerk_y = None
        jerk_z = None
        jerk_mag = None
        if self._last_sample_ts is not None and self._last_accel_g is not None:
            dt = now - self._last_sample_ts
            if dt > 0:
                jerk_x = (accel_x_g - self._last_accel_g[0]) / dt
                jerk_y = (accel_y_g - self._last_accel_g[1]) / dt
                jerk_z = (accel_z_g - self._last_accel_g[2]) / dt
                jerk_mag = math.sqrt(jerk_x**2 + jerk_y**2 + jerk_z**2)
            else:
                dt = None

        self._last_sample_ts = now
        self._last_accel_g = (accel_x_g, accel_y_g, accel_z_g)

        return IMUState(
            ts_unix_ms=ts_unix_ms,
            chip=self.chip,
            address=self._address_str(),
            bus=self.bus_num,
            accel_x_g=float(accel_x_g),
            accel_y_g=float(accel_y_g),
            accel_z_g=float(accel_z_g),
            accel_x_ms2=float(accel_x_ms2),
            accel_y_ms2=float(accel_y_ms2),
            accel_z_ms2=float(accel_z_ms2),
            gyro_x_dps=float(gyro_x_dps),
            gyro_y_dps=float(gyro_y_dps),
            gyro_z_dps=float(gyro_z_dps),
            temp_c=float(temp_c),
            accel_mag_g=float(accel_mag_g),
            accel_mag_ms2=float(accel_mag_ms2),
            jerk_x_gps=float(jerk_x) if jerk_x is not None else None,
            jerk_y_gps=float(jerk_y) if jerk_y is not None else None,
            jerk_z_gps=float(jerk_z) if jerk_z is not None else None,
            jerk_mag_gps=float(jerk_mag) if jerk_mag is not None else None,
            sample_dt_sec=float(dt) if dt is not None else None,
            imu_ok=True,
            raw={
                "accel": {"x": accel_x_raw, "y": accel_y_raw, "z": accel_z_raw},
                "gyro": {"x": gyro_x_raw, "y": gyro_y_raw, "z": gyro_z_raw},
                "temp": temp_raw,
            },
        )

    @staticmethod
    def _mpu_chip_name(who_am_i: int) -> str:
        known = {
            0x68: "MPU6050_OR_COMPATIBLE",
            0x70: "MPU6500",
            0x71: "MPU9250",
            0x73: "MPU9255",
        }
        return known.get(int(who_am_i), f"MPU_SERIES_UNKNOWN_0x{int(who_am_i):02X}")

    @staticmethod
    def _to_int16_be(hi: int, lo: int) -> int:
        val = (int(hi) << 8) | int(lo)
        return val - 65536 if val & 0x8000 else val

    def _address_str(self) -> Optional[str]:
        return f"0x{self.address:02X}" if self.address is not None else None

    def _log_read_warning(self, message: str, *args) -> None:
        now = time.time()
        if (now - self._last_read_warn_ts) >= 5.0:
            log.warning(message, *args)
            self._last_read_warn_ts = now

