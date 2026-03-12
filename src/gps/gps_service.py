import serial
import pynmea2
import logging
from typing import Optional, Dict

log = logging.getLogger(__name__)


class GPSService:
    """
    Reads GPS data from UART and parses NMEA sentences.
    """

    def __init__(self, port: str, baud: int):
        self.port = port
        self.baud = int(baud)
        self.serial = None

        self.state = {
            "lat": None,
            "lng": None,
            "speed_kmph": None,
            "satellites": None,
            "hdop": None,
            "course_deg": None,
            "gps_fix": False,
        }

    def connect(self):
        try:
            self.serial = serial.Serial(self.port, self.baud, timeout=1)
            log.info("GPS serial opened: %s @ %s", self.port, self.baud)
        except Exception as e:
            log.error("Failed to open GPS serial: %s", e)

    def read(self) -> Optional[Dict]:
        if not self.serial:
            return None

        try:
            line = self.serial.readline().decode("ascii", errors="ignore").strip()
            if not line.startswith("$"):
                return None

            msg = pynmea2.parse(line)

            if isinstance(msg, pynmea2.types.talker.GGA):
                self.state["satellites"] = int(msg.num_sats) if msg.num_sats else None
                self.state["hdop"] = float(msg.horizontal_dil) if msg.horizontal_dil else None
                self.state["gps_fix"] = msg.gps_qual != "0"

            if isinstance(msg, pynmea2.types.talker.RMC):
                if msg.latitude and msg.longitude:
                    self.state["lat"] = float(msg.latitude)
                    self.state["lng"] = float(msg.longitude)

                if msg.spd_over_grnd:
                    self.state["speed_kmph"] = float(msg.spd_over_grnd) * 1.852

                if msg.true_course:
                    self.state["course_deg"] = float(msg.true_course)

            return self.state

        except Exception:
            return None

    def close(self):
        if self.serial:
            try:
                self.serial.close()
            except Exception:
                pass