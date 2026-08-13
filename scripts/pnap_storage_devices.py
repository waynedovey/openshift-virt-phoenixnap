#!/usr/bin/env python3
"""Parse phoenixNAP server storage descriptions into a conservative physical-device count.

phoenixNAP exposes storage as a human-readable string (for example ``2x 1TB NVMe``).
This helper deliberately returns zero when the description cannot be understood so callers
fail closed rather than accidentally selecting a single-disk server for an LVMS layout.
"""

from __future__ import annotations

import argparse
import json
import re

# Common provider forms: "2x 1TB NVMe", "2 x 1 TB NVMe", "2×960GB SSD".
_MULTIPLICITY = re.compile(r"(?i)(?<![A-Za-z0-9_.])(\d+)\s*[x×]\s*(?=\d)")
# Conservative single-device fallback when a description contains exactly one recognizable
# capacity/media pair but omits an explicit "1x" quantity.
_SINGLE_DEVICE = re.compile(r"(?i)\b\d+(?:\.\d+)?\s*(?:TB|GB)\b[^,+;/]*\b(?:NVME|SSD|HDD)\b")


def count_storage_devices(storage: object) -> int:
    """Return the number of physical storage devices described, or 0 if unknown."""
    if not isinstance(storage, str):
        return 0
    text = storage.strip()
    if not text:
        return 0

    multiplicities = [int(value) for value in _MULTIPLICITY.findall(text)]
    if multiplicities:
        return sum(multiplicities)

    # If no quantity notation exists, only accept an unambiguous single capacity/media
    # description. Multiple clauses without explicit counts are treated as unknown.
    singles = _SINGLE_DEVICE.findall(text)
    return 1 if len(singles) == 1 else 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--storage", required=True)
    args = parser.parse_args()
    count = count_storage_devices(args.storage)
    print(json.dumps({"storage": args.storage, "storageDeviceCount": count}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
