import argparse
import logging
import time

from src.compass.compass_service import CompassService


def main():
    parser = argparse.ArgumentParser(description="Standalone compass test")
    parser.add_argument("--bus", type=int, default=1)
    parser.add_argument("--address", default="auto")
    parser.add_argument("--offset", type=float, default=0.0)
    parser.add_argument("--declination", type=float, default=0.0)
    parser.add_argument("--interval", type=float, default=1.0)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    compass = CompassService(
        bus=args.bus,
        address=args.address,
        heading_offset_deg=args.offset,
        declination_deg=args.declination,
    )
    compass.connect()

    if not compass.connected:
        print("Compass not detected or unsupported. On Raspberry Pi, install dependency with: pip install smbus2")

    try:
        while True:
            state = compass.read()
            if state is None:
                print("Compass: no reading")
            else:
                print(
                    "chip={chip} address={address} heading_raw_deg={raw} heading_deg={heading} "
                    "mag_x={x} mag_y={y} mag_z={z} compass_fix={fix}".format(
                        chip=state.chip,
                        address=state.address,
                        raw=state.heading_raw_deg,
                        heading=state.heading_deg,
                        x=state.mag_x,
                        y=state.mag_y,
                        z=state.mag_z,
                        fix=state.compass_fix,
                    )
                )
            time.sleep(max(0.0, float(args.interval)))
    except KeyboardInterrupt:
        print("\nStopped by user.")
    finally:
        compass.close()


if __name__ == "__main__":
    main()
