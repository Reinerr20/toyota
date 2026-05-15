import argparse
import logging
import time
from datetime import datetime

from src.compass.compass_service import CompassService
from src.gps.gps_publisher import GPSPublisher
from src.gps.gps_worker import GPSWorker
from src.gps.models import GPSState


def run_real_mode(args, publisher, compass_service=None):
    worker = GPSWorker(
        port=args.port,
        baud=args.baud,
        poll_interval_sec=args.poll_interval,
        publisher=publisher,
        send_interval_sec=args.send_interval,
        compass_service=compass_service,
        compass_publish_enabled=args.compass_enabled,
    )

    try:
        worker.start()
        print("Live dashboard GPS test started (REAL GPS mode). Press Ctrl+C to stop.")

        while True:
            state = worker.get_latest()
            print(
                f"fix={state.gps_fix} lat={state.lat} lng={state.lng} "
                f"sats={state.satellites} hdop={state.hdop} speed={state.speed_kmph} "
                f"seq={getattr(state, 'seq', None)} "
                f"ts={getattr(state, 'ts_unix_ms', None)} "
                f"ts_readable={ms_to_readable_local(getattr(state, 'ts_unix_ms', None))} "
                f"gps_read_ts={getattr(state, 'gps_read_ts_unix_ms', None)} "
                f"gps_read_ts_readable={ms_to_readable_local(getattr(state, 'gps_read_ts_unix_ms', None))} "
                f"heading_deg={getattr(state, 'heading_deg', None)}"
            )
            time.sleep(2)

    except KeyboardInterrupt:
        print("\nStopped by user.")
    finally:
        worker.close()


def ms_to_readable_local(ms):
    if ms is None:
        return None
    dt = datetime.fromtimestamp(ms / 1000)
    return dt.strftime("%Y-%m-%d %H:%M:%S.") + f"{dt.microsecond // 1000:03d} WIB"


def run_mock_mode(args, publisher):
    if args.mock_start_lat is None or args.mock_start_lng is None:
        raise SystemExit(
            "--mock butuh --mock-start-lat dan --mock-start-lng"
        )

    lat = args.mock_start_lat
    lng = args.mock_start_lng
    seq = 0

    print("Live dashboard GPS test started (MOCK mode). Press Ctrl+C to stop.")

    try:
        while True:
            now_ms = int(time.time() * 1000)
            seq += 1

            state = GPSState(
                lat=lat,
                lng=lng,
                speed_kmph=args.mock_speed,
                satellites=args.mock_satellites,
                hdop=args.mock_hdop,
                gps_fix=True,
                last_sentence="MOCK",
                source_port="MOCK",
                raw_line="MOCK",
                gps_read_ts_unix_ms=now_ms - args.mock_read_lag_ms,
                ts_unix_ms=now_ms,
                seq=seq,
            )

            ok = publisher.send_location(state)
            if ok:
                print(
                    f"mock_sent={ok} lat={state.lat} lng={state.lng} "
                    f"speed={state.speed_kmph} seq={state.seq} "
                    f"ts={state.ts_unix_ms} "
                    f"ts_readable={ms_to_readable_local(state.ts_unix_ms)} "
                    f"gps_read_ts={state.gps_read_ts_unix_ms} "
                    f"gps_read_ts_readable={ms_to_readable_local(state.gps_read_ts_unix_ms)}"
                )
            else:
                print("error send location")

            lat += args.mock_step_lat
            lng += args.mock_step_lng
            time.sleep(args.send_interval)

    except KeyboardInterrupt:
        print("\nStopped by user.")


def main():
    parser = argparse.ArgumentParser(description="Live GPS dashboard test")
    parser.add_argument("--port", default="/dev/ttyAMA0")
    parser.add_argument("--baud", type=int, default=9600)
    parser.add_argument("--vehicle-id", required=True)
    parser.add_argument("--ws-url", required=True)
    parser.add_argument("--poll-interval", type=float, default=0.2)
    parser.add_argument("--send-interval", type=float, default=2.0)

    # Optional compass mode for real GPS test
    parser.add_argument("--compass-enabled", action="store_true")
    parser.add_argument("--compass-bus", type=int, default=1)
    parser.add_argument("--compass-address", default="auto")
    parser.add_argument("--compass-offset", type=float, default=0.0)
    parser.add_argument("--compass-declination", type=float, default=0.0)

    # Mock mode
    parser.add_argument("--mock", action="store_true", help="Use mock GPS data instead of serial GPS")
    parser.add_argument("--mock-start-lat", type=float)
    parser.add_argument("--mock-start-lng", type=float)
    parser.add_argument("--mock-step-lat", type=float, default=0.00005)
    parser.add_argument("--mock-step-lng", type=float, default=0.00005)
    parser.add_argument("--mock-speed", type=float, default=12.0)
    parser.add_argument("--mock-satellites", type=int, default=7)
    parser.add_argument("--mock-hdop", type=float, default=1.2)
    parser.add_argument("--mock-read-lag-ms", type=int, default=150)

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    publisher = GPSPublisher(
        vehicle_id=args.vehicle_id,
        ws_url=args.ws_url,
    )
    compass_service = None

    try:
        if args.mock:
            run_mock_mode(args, publisher)
        else:
            if args.compass_enabled:
                compass_service = CompassService(
                    bus=args.compass_bus,
                    address=args.compass_address,
                    heading_offset_deg=args.compass_offset,
                    declination_deg=args.compass_declination,
                )
                compass_service.connect()
                if not getattr(compass_service, "connected", False):
                    compass_service = None

            run_real_mode(args, publisher, compass_service=compass_service)
    finally:
        if compass_service is not None:
            compass_service.close()
        publisher.close()


if __name__ == "__main__":
    main()
