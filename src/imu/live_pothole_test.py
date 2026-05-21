import argparse
import logging
import time

from src.imu.imu_publisher import IMUPublisher
from src.imu.imu_service import IMUService
from src.imu.imu_worker import IMUWorker

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger(__name__)


def _fmt(value, precision: int = 3) -> str:
    if value is None:
        return "None"
    if isinstance(value, float):
        return f"{value:.{precision}f}"
    return str(value)


def _gps_value(gps_state, key, default=None):
    if gps_state is None:
        return default
    if isinstance(gps_state, dict):
        return gps_state.get(key, default)
    return getattr(gps_state, key, default)


def main() -> None:
    parser = argparse.ArgumentParser(description="Standalone IMU pothole telemetry test")
    parser.add_argument("--bus", type=int, default=1)
    parser.add_argument("--address", default="auto")
    parser.add_argument("--vehicle-id", default="1210")
    parser.add_argument("--post-url", default="http://203.100.57.59:3000/api/v1/pothole/add")
    parser.add_argument("--post-enabled", action="store_true")
    parser.add_argument("--sample-hz", type=float, default=25.0)
    parser.add_argument("--send-interval", type=float, default=1.0)
    parser.add_argument("--gps-port", default="/dev/ttyAMA0")
    parser.add_argument("--gps-baud", type=int, default=9600)
    parser.add_argument("--gps-enabled", action="store_true")
    parser.add_argument("--compat-payload", action="store_true")
    parser.add_argument("--print-payload", action="store_true")
    parser.add_argument("--mock-gps-lat", type=float, default=None)
    parser.add_argument("--mock-gps-lng", type=float, default=None)
    parser.add_argument("--mock-gps-speed-kmh", type=float, default=0.0)
    parser.add_argument("--mock-gps-satellites", type=int, default=0)
    parser.add_argument("--pothole-detection-enabled", action="store_true")
    parser.add_argument("--min-speed-kmph", type=float, default=5.0)
    parser.add_argument("--accel-mag-threshold-g", type=float, default=1.8)
    parser.add_argument("--jerk-mag-threshold-gps", type=float, default=8.0)
    parser.add_argument("--event-cooldown-sec", type=float, default=2.0)
    args = parser.parse_args()

    gps_worker = None
    imu_worker = None
    mock_gps = None

    if args.mock_gps_lat is not None and args.mock_gps_lng is not None:
        mock_gps = {
            "lat": args.mock_gps_lat,
            "lng": args.mock_gps_lng,
            "speed_kmph": args.mock_gps_speed_kmh,
            "satellites": args.mock_gps_satellites,
        }

    try:
        if args.gps_enabled:
            try:
                from src.gps.gps_worker import GPSWorker

                gps_worker = GPSWorker(port=args.gps_port, baud=args.gps_baud)
                gps_worker.start()
            except Exception as e:
                log.warning("GPS disabled for this test: %s", e)
                gps_worker = None

        imu_service = IMUService(bus=args.bus, address=args.address)
        imu_service.connect()
        if not imu_service.is_connected():
            log.warning("IMU not detected")
            return

        publisher = IMUPublisher(
            post_url=args.post_url,
            vehicle_id=args.vehicle_id,
            enabled=args.post_enabled,
        )
        imu_worker = IMUWorker(
            imu_service=imu_service,
            publisher=publisher,
            gps_provider=gps_worker.get_latest if gps_worker else None,
            sample_hz=args.sample_hz,
            send_interval_sec=args.send_interval,
            publish_enabled=args.post_enabled,
            pothole_detection_enabled=args.pothole_detection_enabled,
            min_speed_kmph=args.min_speed_kmph,
            accel_mag_threshold_g=args.accel_mag_threshold_g,
            jerk_mag_threshold_gps=args.jerk_mag_threshold_gps,
            event_cooldown_sec=args.event_cooldown_sec,
            compat_payload=args.compat_payload,
            mock_gps=mock_gps,
            print_payload=args.print_payload,
        )
        imu_worker.start()

        while True:
            time.sleep(1.0)
            state = imu_worker.get_latest()
            candidate = imu_worker.get_latest_candidate()
            gps_state = gps_worker.get_latest() if gps_worker else None
            effective_gps_state = imu_worker._effective_gps_state(gps_state)
            posted = imu_worker.get_last_payload_sent()

            if state is None:
                print("IMU: waiting for sample", flush=True)
                continue

            gps_text = "disabled"
            if effective_gps_state is not None:
                gps_source = "mock" if isinstance(effective_gps_state, dict) else "real"
                gps_text = (
                    f"source={gps_source} fix={getattr(effective_gps_state, 'gps_fix', None)} "
                    f"lat={_fmt(_gps_value(effective_gps_state, 'lat'), 6)} "
                    f"lng={_fmt(_gps_value(effective_gps_state, 'lng'), 6)} "
                    f"speed_kmph={_fmt(_gps_value(effective_gps_state, 'speed_kmph'))} "
                    f"sats={_gps_value(effective_gps_state, 'satellites')} "
                    f"hdop={_fmt(_gps_value(effective_gps_state, 'hdop'))}"
                )

            print(
                "IMU chip={chip} address={address} accel_g=({ax},{ay},{az}) "
                "accel_mag_g={amag} gyro_dps=({gx},{gy},{gz}) jerk_mag_gps={jerk} "
                "temp_c={temp} gps=[{gps}] posted={posted} pothole_candidate={cand} "
                "severity={severity} reason={reason}".format(
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
                    gps=gps_text,
                    posted=posted,
                    cand=candidate.is_candidate,
                    severity=candidate.severity,
                    reason=candidate.reason,
                ),
                flush=True,
            )
    except KeyboardInterrupt:
        pass
    finally:
        if imu_worker is not None:
            imu_worker.close()
        if gps_worker is not None:
            gps_worker.close()


if __name__ == "__main__":
    main()
