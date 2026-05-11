import argparse
import logging
import time

from src.gps.gps_publisher import GPSPublisher
from src.gps.gps_worker import GPSWorker
from src.gps.models import GPSState
from datetime import datetime


def run_real_mode(args, publisher):
    worker = GPSWorker(
        port=args.port,
        baud=args.baud,
        poll_interval_sec=args.poll_interval,
        publisher=publisher,
        send_interval_sec=args.send_interval,
    )

def ms_to_readable_local(ms):
    if ms is None:
        return None
    dt = datetime.fromtimestamp(ms / 1000)
    return dt.strftime("%Y-%m-%d %H:%M:%S.") + f"{dt.microsecond // 1000:03d} WIB"

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
                f"gps_read_ts_readable={ms_to_readable_local(getattr(state, 'gps_read_ts_unix_ms', None))}"
            )
            time.sleep(2)

    except KeyboardInterrupt:
        print("\nStopped by user.")
    finally:
        worker.close()


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

            if ok :
                 print(
                f"mock_sent={ok} lat={state.lat} lng={state.lng} "
                f"speed={state.speed_kmph} seq={state.seq} "
                f"ts={state.ts_unix_ms} "
                f"ts_readable={ms_to_readable_local(state.ts_unix_ms)} "
                f"gps_read_ts={state.gps_read_ts_unix_ms} "
                f"gps_read_ts_readable={ms_to_readable_local(state.gps_read_ts_unix_ms)}"
            )
                 
                #  // check local storage 
                #  // jika ada kirim dan clear
                #  // jika tidak skip
            else :
                print(
                    f"error send location"
                )
                
            #  location kedalam 1 local storage dengan interval 1 menit

           

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

    try:
        if args.mock:
            run_mock_mode(args, publisher)
        else:
            run_real_mode(args, publisher)
    finally:
        publisher.close()


if __name__ == "__main__":
    main()