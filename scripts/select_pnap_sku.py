#!/usr/bin/env python3
"""Select phoenixNAP Bare Metal Cloud server SKUs by live stock, hourly price, and lab sizing.

Uses the phoenixNAP Billing API only. The bearer token is read from PNAP_ACCESS_TOKEN and
is never printed. Output is sanitized JSON suitable for Ansible's from_json filter.

A logical site can be given more than one physical location, for example:
  --site sw1=PHX,ASH,NLD --site c1=PHX,ASH,NLD --distinct-locations
This lets a two-site lab survive temporary regional stock shortages while still ensuring
that the two OpenShift clusters land in separate phoenixNAP regions.
"""

from __future__ import annotations

import argparse
import itertools
import json
import os
import sys
import urllib.parse
import urllib.request
from typing import Any

from pnap_storage_devices import count_storage_devices


def api_get(base: str, path: str, token: str, params: dict[str, Any]) -> Any:
    query = urllib.parse.urlencode(params, doseq=True)
    url = f"{base.rstrip('/')}{path}?{query}"
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def parse_site(value: str) -> tuple[str, list[str]]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("site must be NAME=LOCATION[,LOCATION...], for example sw1=PHX,ASH,NLD")
    name, raw_locations = value.split("=", 1)
    name = name.strip()
    locations = []
    for raw in raw_locations.split(","):
        location = raw.strip().upper()
        if location and location not in locations:
            locations.append(location)
    if not name or not locations:
        raise argparse.ArgumentTypeError("site must contain a name and at least one location")
    return name, locations


def candidate_shortfall(c: dict[str, Any], preferred_ram: float, preferred_cores: float) -> float:
    ram_short = max(0.0, preferred_ram - c["ramInGb"]) / max(preferred_ram, 1.0)
    core_short = max(0.0, preferred_cores - c["cores"]) / max(preferred_cores, 1.0)
    return ram_short + core_short


def candidate_sort_key(c: dict[str, Any], preferred_ram: float, preferred_cores: float):
    return (
        candidate_shortfall(c, preferred_ram, preferred_cores),
        float(c["hourlyPrice"]),
        -float(c["ramInGb"]),
        -float(c["cores"]),
        c["productCode"],
        c.get("location", ""),
    )


def sanitize_product(product: dict[str, Any], plan: dict[str, Any], available_quantity: int) -> dict[str, Any]:
    metadata = product.get("metadata") or {}
    cpu_count = float(metadata.get("cpuCount") or 0)
    cores_per_cpu = float(metadata.get("coresPerCpu") or 0)
    cores = cpu_count * cores_per_cpu
    if cores.is_integer():
        cores = int(cores)
    ram = float(metadata.get("ramInGb") or 0)
    if ram.is_integer():
        ram = int(ram)
    return {
        "productCode": product.get("productCode", ""),
        "location": plan.get("location", ""),
        "hourlyPrice": float(plan.get("price", 0)),
        "priceUnit": plan.get("priceUnit", ""),
        "pricingModel": plan.get("pricingModel", ""),
        "sku": plan.get("sku", ""),
        "availableQuantity": int(available_quantity),
        "ramInGb": ram,
        "cores": cores,
        "cpu": metadata.get("cpu", ""),
        "cpuCount": cpu_count,
        "coresPerCpu": cores_per_cpu,
        "cpuFrequency": metadata.get("cpuFrequency", 0),
        "network": metadata.get("network", ""),
        "storage": metadata.get("storage", ""),
        "storageDeviceCount": count_storage_devices(metadata.get("storage", "")),
    }


def live_location_candidates(
    api_base: str,
    token: str,
    location: str,
    min_ram_gb: float,
    min_cores: float,
    min_storage_devices: int,
) -> list[dict[str, Any]]:
    """Return all live HOURLY candidates that meet hardware minimums, regardless of budget."""
    products = api_get(
        api_base,
        "/billing/v1/products",
        token,
        {"productCategory": "SERVER", "location": location},
    )
    availability = api_get(
        api_base,
        "/billing/v1/product-availability",
        token,
        {
            "productCategory": "SERVER",
            "location": location,
            "minQuantity": 1,
            "showOnlyMinQuantityAvailable": "true",
        },
    )

    live: dict[str, int] = {}
    for item in availability or []:
        code = item.get("productCode")
        for detail in item.get("locationAvailabilityDetails") or []:
            if (
                code
                and detail.get("location") == location
                and detail.get("minQuantityAvailable") is True
                and int(detail.get("availableQuantity") or 0) > 0
            ):
                live[code] = max(live.get(code, 0), int(detail.get("availableQuantity") or 0))

    candidates: list[dict[str, Any]] = []
    for product in products or []:
        code = product.get("productCode")
        if not code or code not in live:
            continue
        metadata = product.get("metadata") or {}
        ram = float(metadata.get("ramInGb") or 0)
        cores = float(metadata.get("cpuCount") or 0) * float(metadata.get("coresPerCpu") or 0)
        storage_device_count = count_storage_devices(metadata.get("storage", ""))
        if ram < min_ram_gb or cores < min_cores or storage_device_count < min_storage_devices:
            continue

        hourly_plans = [
            p
            for p in (product.get("plans") or [])
            if p.get("location") == location
            and p.get("pricingModel") == "HOURLY"
            and p.get("priceUnit") == "HOUR"
            and float(p.get("price") or 0) > 0
        ]
        if not hourly_plans:
            continue
        plan = min(hourly_plans, key=lambda p: float(p.get("price") or 999999))
        candidates.append(sanitize_product(product, plan, live[code]))

    return candidates


def site_candidates(
    api_base: str,
    token: str,
    location: str,
    max_hourly_price: float,
    min_ram_gb: float,
    min_cores: float,
    min_storage_devices: int,
) -> list[dict[str, Any]]:
    """Backward-compatible single-location budget-qualified selector used by tests."""
    return [
        c
        for c in live_location_candidates(
            api_base,
            token,
            location,
            min_ram_gb,
            min_cores,
            min_storage_devices,
        )
        if float(c["hourlyPrice"]) < max_hourly_price
    ]


def combo_sort_key(
    combo: tuple[dict[str, Any], ...], preferred_ram: float, preferred_cores: float
) -> tuple[Any, ...]:
    # Prefer the pair with the least aggregate sizing shortfall, then the lowest
    # aggregate hourly cost. Deterministic location/product tie breakers keep
    # repeated preflight/deploy runs stable while stock remains unchanged.
    return (
        sum(candidate_shortfall(c, preferred_ram, preferred_cores) for c in combo),
        sum(float(c["hourlyPrice"]) for c in combo),
        tuple(c["productCode"] for c in combo),
        tuple(c["location"] for c in combo),
    )


def choose_distinct_combo(
    names: list[str],
    candidates_by_site: dict[str, list[dict[str, Any]]],
    preferred_ram: float,
    preferred_cores: float,
    prefer_common: bool,
    require_common: bool,
) -> tuple[dict[str, dict[str, Any]] | None, bool]:
    combos = []
    for combo in itertools.product(*(candidates_by_site[name] for name in names)):
        if len({c["location"] for c in combo}) != len(combo):
            continue
        combos.append(combo)

    if not combos:
        return None, False

    common = [combo for combo in combos if len({c["productCode"] for c in combo}) == 1]
    if prefer_common and common:
        combos = common
        used_common = True
    elif require_common:
        if not common:
            return None, False
        combos = common
        used_common = True
    else:
        used_common = False

    combos.sort(key=lambda combo: combo_sort_key(combo, preferred_ram, preferred_cores))
    best = combos[0]
    return {name: row for name, row in zip(names, best)}, used_common


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-base", default="https://api.phoenixnap.com")
    parser.add_argument("--site", action="append", type=parse_site, required=True)
    parser.add_argument("--blocked-location", action="append", default=[])
    parser.add_argument("--distinct-locations", action="store_true")
    parser.add_argument("--max-hourly-price", type=float, required=True)
    parser.add_argument("--min-ram-gb", type=float, default=64)
    parser.add_argument("--min-cores", type=float, default=6)
    parser.add_argument("--min-storage-devices", type=int, default=1)
    parser.add_argument("--preferred-ram-gb", type=float, default=128)
    parser.add_argument("--preferred-cores", type=float, default=8)
    parser.add_argument("--prefer-common", action="store_true")
    parser.add_argument("--require-common", action="store_true")
    parser.add_argument("--top", type=int, default=8)
    args = parser.parse_args()

    token = os.environ.get("PNAP_ACCESS_TOKEN", "")
    if not token:
        print(json.dumps({"ok": False, "error": "PNAP_ACCESS_TOKEN is not set"}))
        return 0

    try:
        blocked = {x.strip().upper() for x in args.blocked_location if x.strip()}
        site_locations: dict[str, list[str]] = {}
        all_locations: list[str] = []
        for name, locations in args.site:
            allowed = [loc for loc in locations if loc not in blocked]
            site_locations[name] = allowed
            for loc in locations:
                if loc not in all_locations:
                    all_locations.append(loc)

        # Query each region only once. regionCandidates intentionally includes
        # live shapes above the configured budget so failure output can show the
        # actual current hourly rate instead of hiding useful provider data.
        region_candidates: dict[str, list[dict[str, Any]]] = {}
        for location in all_locations:
            rows = live_location_candidates(
                args.api_base,
                token,
                location,
                args.min_ram_gb,
                args.min_cores,
                args.min_storage_devices,
            )
            rows.sort(key=lambda c: candidate_sort_key(c, args.preferred_ram_gb, args.preferred_cores))
            for row in rows:
                row["withinBudget"] = float(row["hourlyPrice"]) < args.max_hourly_price
            region_candidates[location] = rows

        candidates_by_site: dict[str, list[dict[str, Any]]] = {}
        for name, locations in site_locations.items():
            rows = [
                dict(c)
                for location in locations
                for c in region_candidates.get(location, [])
                if float(c["hourlyPrice"]) < args.max_hourly_price
            ]
            rows.sort(key=lambda c: candidate_sort_key(c, args.preferred_ram_gb, args.preferred_cores))
            candidates_by_site[name] = rows

        empty = [name for name, items in candidates_by_site.items() if not items]
        if empty:
            searched = sorted({loc for locs in site_locations.values() for loc in locs})
            print(
                json.dumps(
                    {
                        "ok": False,
                        "error": (
                            "No live HOURLY server below ${:.2f}/hour met min {} GB RAM / {} cores / {} physical storage devices "
                            "for site(s): {} after trying all allowed regions: {}"
                        ).format(
                            args.max_hourly_price,
                            int(args.min_ram_gb),
                            int(args.min_cores),
                            int(args.min_storage_devices),
                            ", ".join(empty),
                            ", ".join(searched) or "none",
                        ),
                        "sites": {},
                        "candidates": {k: v[: args.top] for k, v in candidates_by_site.items()},
                        "regionCandidates": {k: v[: args.top] for k, v in region_candidates.items()},
                        "searchedLocations": searched,
                        "blockedLocations": sorted(blocked),
                    },
                    sort_keys=True,
                )
            )
            return 0

        names = list(candidates_by_site)
        selected: dict[str, dict[str, Any]] = {}
        used_common = False

        if args.distinct_locations and len(names) > 1:
            selected_combo, used_common = choose_distinct_combo(
                names,
                candidates_by_site,
                args.preferred_ram_gb,
                args.preferred_cores,
                args.prefer_common,
                args.require_common,
            )
            if selected_combo is None:
                print(
                    json.dumps(
                        {
                            "ok": False,
                            "error": (
                                "Live qualifying capacity exists, but no selection can place all missing sites in distinct regions"
                                + (" with a common SKU" if args.require_common else "")
                            ),
                            "sites": {},
                            "candidates": {k: v[: args.top] for k, v in candidates_by_site.items()},
                            "regionCandidates": {k: v[: args.top] for k, v in region_candidates.items()},
                            "searchedLocations": sorted({loc for locs in site_locations.values() for loc in locs}),
                            "blockedLocations": sorted(blocked),
                        },
                        sort_keys=True,
                    )
                )
                return 0
            selected = selected_combo
        else:
            # One missing site, or explicit fixed-location mode. Prefer a common
            # SKU only has meaning when selecting multiple sites.
            for name in names:
                selected[name] = candidates_by_site[name][0]

        print(
            json.dumps(
                {
                    "ok": True,
                    "commonSkuSelected": used_common,
                    "policy": {
                        "maxHourlyPriceExclusive": args.max_hourly_price,
                        "minRamGb": args.min_ram_gb,
                        "minCores": args.min_cores,
                        "minStorageDevices": args.min_storage_devices,
                        "preferredRamGb": args.preferred_ram_gb,
                        "preferredCores": args.preferred_cores,
                        "distinctLocations": args.distinct_locations,
                    },
                    "sites": selected,
                    "candidates": {k: v[: args.top] for k, v in candidates_by_site.items()},
                    "regionCandidates": {k: v[: args.top] for k, v in region_candidates.items()},
                    "searchedLocations": sorted({loc for locs in site_locations.values() for loc in locs}),
                    "blockedLocations": sorted(blocked),
                },
                sort_keys=True,
            )
        )
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "error": f"phoenixNAP SKU selection failed: {type(exc).__name__}: {exc}"}))
        return 0


if __name__ == "__main__":
    sys.exit(main())
