import copy
import logging
import time
from typing import Optional

import serial
import pynmea2

from src.gps.models import GPSState

log = logging.getLogger(__name__)


class GPSService:
    """
    Serial GPS reader + NMEA parser.
    Responsibility:
    - open serial
    - read line
    - parse NMEA
    - maintain latest GPS state

    No threading.
    No websocket.
    No dashboard logic.
    """

    def __init__(self, port: str = "/dev/serial0", baud: int = 9600, timeout: float = 1.0):
        self.port = port
        self.baud = int(baud)
        self.timeout = float(timeout)
        self.serial_conn = None
        self.state = GPSState(source_port=self.port)

    @property
    def connected(self) -> bool:
        return self.serial_conn is not None and self.serial_conn.is_open

    def connect(self) -> None:
        if self.connected:
            return

        self.serial_conn = serial.Serial(
            port=self.port,
            baudrate=self.baud,
            timeout=self.timeout,
        )
        log.info("GPS serial opened: %s @ %s", self.port, self.baud)

    def close(self) -> None:
        if self.serial_conn is not None:
            try:
                self.serial_conn.close()
            except Exception:
                pass
            self.serial_conn = None
            log.info("GPS serial closed")

    def read_raw_line(self) -> Optional[str]:
        if not self.connected:
            return None

        try:
            line = self.serial_conn.readline().decode("ascii", errors="ignore").strip()
            if not line:
                return None
            return line
        except Exception as e:
            log.debug("GPS raw read error: %s", e)
            return None

    def read(self) -> Optional[GPSState]:
        """
        Read one line, parse if possible, update internal latest state.
        Returns a COPY of latest state only when a valid sentence is processed.
        """
        line = self.read_raw_line()
        if not line:
            return None

        if not line.startswith("$"):
            return None

        try:
            msg = pynmea2.parse(line)
        except Exception as e:
            log.debug("Failed to parse NMEA line: %s | line=%r", e, line)
            return None

        self.state.raw_line = line
        self.state.last_sentence = msg.sentence_type if hasattr(msg, "sentence_type") else None
        self.state.gps_read_ts_unix_ms = int(time.time() * 1000)

        # GGA = satellites / hdop / altitude / fix quality
        if isinstance(msg, pynmea2.types.talker.GGA):
            if msg.num_sats:
                try:
                    self.state.satellites = int(msg.num_sats)
                except Exception:
                    pass

            if msg.horizontal_dil:
                try:
                    self.state.hdop = float(msg.horizontal_dil)
                except Exception:
                    pass

            if msg.altitude:
                try:
                    self.state.altitude_m = float(msg.altitude)
                except Exception:
                    pass

            try:
                self.state.gps_fix = str(msg.gps_qual) != "0"
            except Exception:
                pass

            if msg.latitude and msg.longitude:
                try:
                    self.state.lat = float(msg.latitude)
                    self.state.lng = float(msg.longitude)
                except Exception:
                    pass

            return copy.deepcopy(self.state)

        # RMC = lat/lng/speed/course/status
        if isinstance(msg, pynmea2.types.talker.RMC):
            try:
                self.state.gps_fix = str(msg.status).upper() == "A"
            except Exception:
                pass

            if msg.latitude and msg.longitude:
                try:
                    self.state.lat = float(msg.latitude)
                    self.state.lng = float(msg.longitude)
                except Exception:
                    pass

            if msg.spd_over_grnd:
                try:
                    self.state.speed_kmph = float(msg.spd_over_grnd) * 1.852
                except Exception:
                    pass

            if msg.true_course:
                try:
                    self.state.course_deg = float(msg.true_course)
                except Exception:
                    pass

            return copy.deepcopy(self.state)

        # VTG = speed/course
        if isinstance(msg, pynmea2.types.talker.VTG):
            if msg.spd_over_grnd_kmph:
                try:
                    self.state.speed_kmph = float(msg.spd_over_grnd_kmph)
                except Exception:
                    pass

            if msg.true_track:
                try:
                    self.state.course_deg = float(msg.true_track)
                except Exception:
                    pass

            return copy.deepcopy(self.state)

        return None

    def get_latest(self) -> GPSState:
        return copy.deepcopy(self.state)