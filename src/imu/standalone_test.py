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


def _severity(accel_mag_g: float, jerk_mag_gps: float, accel_threshold_g: float, jerk_threshold_gps: float) -> str:
    accel_ratio = accel_mag_g / accel_threshold_g
    jerk_ratio = jerk_mag_gps / jerk_threshold_gps
    strength = max(accel_ratio, jerk_ratio)
    if strength >= 2.0:
        return "High"
    if strength >= 1.4:
        return "Medium"
    return "Low"


def main() -> None:
    parser = argparse.ArgumentParser(description="Standalone IMU reader")
    parser.add_argument("--bus", type=int, default=1)
    parser.add_argument("--address", default="auto")
    parser.add_argument("--hz", type=float, default=10.0)
    parser.add_argument("--duration", type=float, default=0.0, help="Seconds; 0 means infinite")
    parser.add_argument("--detect", action="store_true", help="Print local shock/pothole candidates")
    parser.add_argument("--accel-threshold-g", type=float, default=1.8)
    parser.add_argument("--jerk-threshold-gps", type=float, default=8.0)
    parser.add_argument("--cooldown-sec", type=float, default=2.0)
    args = parser.parse_args()

    imu = IMUService(bus=args.bus, address=args.address)
    imu.connect()
    if not imu.is_connected():
        log.warning("IMU not detected")
        return

    if args.detect:
        print(
            "Local pothole/shock detection enabled: "
            f"accel_mag_g >= {args.accel_threshold_g:.3f}, "
            f"jerk_mag_gps >= {args.jerk_threshold_gps:.3f}, "
            f"cooldown_sec={args.cooldown_sec:.3f}",
            flush=True,
        )

    period = 1.0 / max(args.hz, 0.1)
    started = time.time()
    last_detection_ts = 0.0
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

                if (
                    args.detect
                    and state.accel_mag_g is not None
                    and state.jerk_mag_gps is not None
                    and state.accel_mag_g >= args.accel_threshold_g
                    and state.jerk_mag_gps >= args.jerk_threshold_gps
                ):
                    now = time.time()
                    if (now - last_detection_ts) >= args.cooldown_sec:
                        severity = _severity(
                            state.accel_mag_g,
                            state.jerk_mag_gps,
                            args.accel_threshold_g,
                            args.jerk_threshold_gps,
                        )
                        print(
                            "[POTHOLE CANDIDATE] severity={severity} "
                            "accel_mag_g={accel} jerk_mag_gps={jerk}".format(
                                severity=severity,
                                accel=_fmt(state.accel_mag_g),
                                jerk=_fmt(state.jerk_mag_gps),
                            ),
                            flush=True,
                        )
                        last_detection_ts = now

            if args.duration > 0 and (time.time() - started) >= args.duration:
                break
            time.sleep(period)
    except KeyboardInterrupt:
        pass
    finally:
        imu.close()


if __name__ == "__main__":
    main()
