import argparse
import logging
import time

from src.imu.imu_service import IMUService

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger(__name__)


def _fmt(value, precision: int = 3) -> str:
    if value is None:
        return "None"
    if isinstance(value, float):
        return f"{value:.{precision}f}"
    return str(value)


def main() -> None:
    parser = argparse.ArgumentParser(description="Standalone IMU reader")
    parser.add_argument("--bus", type=int, default=1)
    parser.add_argument("--address", default="auto")
    parser.add_argument("--hz", type=float, default=10.0)
    parser.add_argument("--duration", type=float, default=0.0, help="Seconds; 0 means infinite")
    args = parser.parse_args()

    imu = IMUService(bus=args.bus, address=args.address)
    imu.connect()
    if not imu.is_connected():
        log.warning("IMU not detected")
        return

    period = 1.0 / max(args.hz, 0.1)
    started = time.time()
    try:
        while True:
            state = imu.read()
            if state is not None:
                print(
                    "chip={chip} address={address} accel_g=({ax},{ay},{az}) "
                    "accel_mag_g={amag} gyro_dps=({gx},{gy},{gz}) jerk_mag_gps={jerk} "
                    "temp_c={temp} imu_ok={ok}".format(
                        chip=state.chip,
                        address=state.address,
                        ax=_fmt(state.accel_x_g),
                        ay=_fmt(state.accel_y_g),
                        az=_fmt(state.accel_z_g),
                        amag=_fmt(state.accel_mag_g),
                        gx=_fmt(state.gyro_x_dps),
                        gy=_fmt(state.gyro_y_dps),
                        gz=_fmt(state.gyro_z_dps),
                        jerk=_fmt(state.jerk_mag_gps),
                        temp=_fmt(state.temp_c, 2),
                        ok=state.imu_ok,
                    ),
                    flush=True,
                )

            if args.duration > 0 and (time.time() - started) >= args.duration:
                break
            time.sleep(period)
    except KeyboardInterrupt:
        pass
    finally:
        imu.close()


if __name__ == "__main__":
    main()

