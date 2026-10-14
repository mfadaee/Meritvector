"""Download the public datasets listed in config/public_data/sources.yaml into data/public/ (checksum-verified).

Usage: python scripts/fetch_public_data.py [--check] [source ...]
  --check  only report which datasets are present and valid; exit 1 if any is missing.
"""

from __future__ import annotations

import sys

from meritvector_analytics.public_data import fetch, sources


def main(argv: list[str]) -> int:
    check = "--check" in argv
    wanted = [a for a in argv if not a.startswith("--")] or list(sources())
    missing = 0
    for sid in wanted:
        src = sources()[sid]
        if check:
            ok = src.available
            missing += not ok
            print(f"{'ok     ' if ok else 'MISSING'} {sid:<11} {src.path}")
            continue
        path = fetch(sid)
        print(f"fetched {sid:<11} {path} ({path.stat().st_size:,} bytes, sha256 verified)")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
