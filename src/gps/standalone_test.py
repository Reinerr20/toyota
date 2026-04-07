import argparse
import logging
import time

from src.gps.gps_service import GPSService


def print_state(state) -> None:
    print("\n------ GPS STATUS ------")
    print("Latitude   :", state.lat)
    print("Longitude  :", state.lng)
    print("Satellites :", state.satellites)
    print("HDOP       :", state.hdop)
    print("Speed km/h :", state.speed_kmph)
    print("Course deg :", state.course_deg)
    print("Altitude m :", state.altitude_m)
    print("GPS Fix    :", state.gps_fix)
    print("Sentence   :", state.last_sentence)
    print("Port       :", state.source_port)
    print("------------------------")


def main():
    parser = argparse.ArgumentParser(description="Standalone GPS test for Raspberry Pi")
    parser.add_argument("--port", default="/dev/serial0", help="Serial port, default=/dev/serial0")
    parser.add_argument("--baud", type=int, default=9600, help="GPS baud rate")
    parser.add_argument("--interval", type=float, default=2.0, help="Print interval in seconds")
    parser.add_argument("--raw", action="store_true", help="Also print raw NMEA lines")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )

    gps = GPSService(port=args.port, baud=args.baud)

    try:
        gps.connect()
        print("GPS connected. Press Ctrl+C to stop.")

        last_print = 0.0

        while True:
            if args.raw:
                raw = gps.read_raw_line()
                if raw:
                    print(raw)
                    # tetap coba parse raw yang baru dibaca?
                    # untuk mode raw, kita nggak parse ulang line yang sama
                    # jadi kita lanjut loop
                time.sleep(0.01)
                continue

            state = gps.read()

            now = time.time()
            if state is not None and (now - last_print) >= args.interval:
                print_state(state)
                last_print = now

            time.sleep(0.01)

    except KeyboardInterrupt:
        print("\nStopped by user.")
    finally:
        gps.close()


if __name__ == "__main__":
    main()