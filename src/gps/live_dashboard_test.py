import argparse
import logging
import time

from src.gps.gps_publisher import GPSPublisher
from src.gps.gps_worker import GPSWorker


def main():
    parser = argparse.ArgumentParser(description="Live GPS dashboard test")
    parser.add_argument("--port", default="/dev/ttyAMA0")
    parser.add_argument("--baud", type=int, default=9600)
    parser.add_argument("--vehicle-id", default="1210")
    parser.add_argument("--ws-url", required=True)
    parser.add_argument("--poll-interval", type=float, default=0.2)
    parser.add_argument("--send-interval", type=float, default=2.0)
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    publisher = GPSPublisher(
        vehicle_id=args.vehicle_id,
        ws_url=args.ws_url,
    )

    worker = GPSWorker(
        port=args.port,
        baud=args.baud,
        poll_interval_sec=args.poll_interval,
        publisher=publisher,
        send_interval_sec=args.send_interval,
    )

    try:
        worker.start()
        print("Live dashboard GPS test started. Press Ctrl+C to stop.")

        while True:
            state = worker.get_latest()
            print(
                f"fix={state.gps_fix} lat={state.lat} lng={state.lng} "
                f"sats={state.satellites} hdop={state.hdop} speed={state.speed_kmph}"
            )
            time.sleep(2)

    except KeyboardInterrupt:
        print("\nStopped by user.")
    finally:
        worker.close()
        publisher.close()


if __name__ == "__main__":
    main()