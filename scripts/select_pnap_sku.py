#!/usr/bin/env python3
"""Select phoenixNAP Bare Metal Cloud server SKUs by live stock, hourly price, and lab sizing.

Uses the phoenixNAP Billing API only. The bearer token is read from PNAP_ACCESS_TOKEN and
is never printed. Output is sanitized JSON suitable for Ansible's from_json filter.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
from typing import Any


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


def parse_site(value: str) -> tuple[str, str]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("site must be NAME=LOCATION, for example sw1=PHX")
    name, location = value.split("=", 1)
    name, location = name.strip(), location.strip().upper()
    if not name or not location:
        raise argparse.ArgumentTypeError("site must contain both NAME and LOCATION")
    return name, location


def candidate_shortfall(c: dict[str, Any], preferred_ram: float, preferred_cores: float) -> float:
    ram_short = max(0.0, preferred_ram - c["ramInGb"]) / max(preferred_ram, 1.0)
    core_short = max(0.0, preferred_cores - c["cores"]) / max(preferred_cores, 1.0)
    return ram_short + core_short


def candidate_sort_key(c: dict[str, Any], preferred_ram: float, preferred_cores: float):
    # First choose the smallest sizing shortfall, then the lowest price. If candidates have the
    # same suitability and cost, prefer more RAM and CPU. This avoids spending up to the entire
    # cap just because a much larger server exists.
    return (
        candidate_shortfall(c, preferred_ram, preferred_cores),
        float(c["hourlyPrice"]),
        -float(c["ramInGb"]),
        -float(c["cores"]),
        c["productCode"],
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
    }


def site_candidates(
    api_base: str,
    token: str,
    location: str,
    max_hourly_price: float,
    min_ram_gb: float,
    min_cores: float,
) -> list[dict[str, Any]]:
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
        if ram < min_ram_gb or cores < min_cores:
            continue

        hourly_plans = [
            p
            for p in (product.get("plans") or [])
            if p.get("location") == location
            and p.get("pricingModel") == "HOURLY"
            and p.get("priceUnit") == "HOUR"
            and float(p.get("price") or 0) > 0
            and float(p.get("price") or 0) < max_hourly_price
        ]
        if not hourly_plans:
            continue
        plan = min(hourly_plans, key=lambda p: float(p.get("price") or 999999))
        candidates.append(sanitize_product(product, plan, live[code]))

    return candidates


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-base", default="https://api.phoenixnap.com")
    parser.add_argument("--site", action="append", type=parse_site, required=True)
    parser.add_argument("--max-hourly-price", type=float, required=True)
    parser.add_argument("--min-ram-gb", type=float, default=64)
    parser.add_argument("--min-cores", type=float, default=6)
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
        candidates_by_site: dict[str, list[dict[str, Any]]] = {}
        locations: dict[str, str] = {}
        for name, location in args.site:
            locations[name] = location
            candidates = site_candidates(
                args.api_base,
                token,
                location,
                args.max_hourly_price,
                args.min_ram_gb,
                args.min_cores,
            )
            candidates.sort(key=lambda c: candidate_sort_key(c, args.preferred_ram_gb, args.preferred_cores))
            candidates_by_site[name] = candidates

        empty = [name for name, items in candidates_by_site.items() if not items]
        if empty:
            print(
                json.dumps(
                    {
                        "ok": False,
                        "error": (
                            "No live HOURLY server below ${:.2f}/hour met min {} GB RAM / {} cores in: {}"
                        ).format(args.max_hourly_price, int(args.min_ram_gb), int(args.min_cores), ", ".join(empty)),
                        "sites": {},
                        "candidates": {k: v[: args.top] for k, v in candidates_by_site.items()},
                    }
                )
            )
            return 0

        names = list(candidates_by_site)
        common_codes = set(c["productCode"] for c in candidates_by_site[names[0]])
        for name in names[1:]:
            common_codes &= {c["productCode"] for c in candidates_by_site[name]}

        selected: dict[str, dict[str, Any]] = {}
        used_common = False
        if args.prefer_common and common_codes:
            # Score common SKUs against the worst location price, while preserving the
            # preferred sizing target. The metadata is product-wide, but prices are location-specific.
            common_options = []
            for code in common_codes:
                rows = [next(c for c in candidates_by_site[n] if c["productCode"] == code) for n in names]
                representative = dict(rows[0])
                representative["hourlyPrice"] = max(float(r["hourlyPrice"]) for r in rows)
                common_options.append((representative, rows))
            common_options.sort(
                key=lambda pair: candidate_sort_key(pair[0], args.preferred_ram_gb, args.preferred_cores)
            )
            _, rows = common_options[0]
            for name, row in zip(names, rows):
                selected[name] = row
            used_common = True
        elif args.require_common:
            print(
                json.dumps(
                    {
                        "ok": False,
                        "error": "No common live SKU met the budget/sizing policy across all requested sites",
                        "sites": {},
                        "candidates": {k: v[: args.top] for k, v in candidates_by_site.items()},
                    }
                )
            )
            return 0
        else:
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
                        "preferredRamGb": args.preferred_ram_gb,
                        "preferredCores": args.preferred_cores,
                    },
                    "sites": selected,
                    "candidates": {k: v[: args.top] for k, v in candidates_by_site.items()},
                },
                sort_keys=True,
            )
        )
        return 0
    except Exception as exc:  # Return only a sanitized message; never echo request headers/token.
        print(json.dumps({"ok": False, "error": f"phoenixNAP SKU selection failed: {type(exc).__name__}: {exc}"}))
        return 0


if __name__ == "__main__":
    sys.exit(main())
