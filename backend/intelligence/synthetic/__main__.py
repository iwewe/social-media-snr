"""`python -m intelligence.synthetic --out DIR [--seed N]`."""

import argparse
from pathlib import Path

from .generator import DEFAULT_SEED, write


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Hasilkan dataset sintetis I2 dan kunci jawabannya."
    )
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = parser.parse_args()
    bundle = write(args.out, args.seed)
    print(
        f"{len(bundle.datasets)} dataset ditulis ke {args.out / 'datasets'}; "
        f"kunci jawaban: {args.out / 'ground-truth.json'}"
    )


if __name__ == "__main__":
    main()
