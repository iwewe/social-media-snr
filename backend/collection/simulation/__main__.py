"""`python -m collection.simulation [--host H] [--port P]`: jalankan simulasi untuk demo/dev."""

import argparse
import time

from .server import SimulationServer


def main() -> None:
    parser = argparse.ArgumentParser(description="Simulasi platform sosial SNR (data sintetis).")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    with SimulationServer(args.host, args.port) as sim:
        print(f"Simulasi berjalan di {sim.base_url} (Ctrl+C untuk berhenti)", flush=True)
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
