import importlib.util
from pathlib import Path
import sys
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from pnap_storage_devices import count_storage_devices  # noqa: E402
import select_pnap_sku  # noqa: E402


class StorageDescriptionTests(unittest.TestCase):
    def test_common_provider_formats(self):
        cases = {
            "1x 1TB NVMe": 1,
            "2x 1TB NVMe": 2,
            "2 x 960GB SSD": 2,
            "2×960GB SSD": 2,
            "1x 480GB SSD + 2x 1TB NVMe": 3,
            "1TB NVMe": 1,
            "": 0,
            "unknown": 0,
        }
        for storage, expected in cases.items():
            with self.subTest(storage=storage):
                self.assertEqual(count_storage_devices(storage), expected)


class SelectorStoragePolicyTests(unittest.TestCase):
    def setUp(self):
        self.original_api_get = select_pnap_sku.api_get

    def tearDown(self):
        select_pnap_sku.api_get = self.original_api_get

    def test_one_disk_sku_is_rejected_when_two_are_required(self):
        products = [
            {
                "productCode": "one.disk",
                "metadata": {
                    "ramInGb": 64,
                    "cpuCount": 1,
                    "coresPerCpu": 8,
                    "storage": "1x 1TB NVMe",
                },
                "plans": [
                    {
                        "location": "ASH",
                        "pricingModel": "HOURLY",
                        "priceUnit": "HOUR",
                        "price": 0.10,
                        "sku": "one-disk-hourly",
                    }
                ],
            },
            {
                "productCode": "two.disk",
                "metadata": {
                    "ramInGb": 64,
                    "cpuCount": 1,
                    "coresPerCpu": 8,
                    "storage": "2x 1TB NVMe",
                },
                "plans": [
                    {
                        "location": "ASH",
                        "pricingModel": "HOURLY",
                        "priceUnit": "HOUR",
                        "price": 0.20,
                        "sku": "two-disk-hourly",
                    }
                ],
            },
        ]
        availability = [
            {
                "productCode": code,
                "locationAvailabilityDetails": [
                    {
                        "location": "ASH",
                        "minQuantityAvailable": True,
                        "availableQuantity": 1,
                    }
                ],
            }
            for code in ("one.disk", "two.disk")
        ]

        def fake_api_get(_base, path, _token, _params):
            return products if path.endswith("/products") else availability

        select_pnap_sku.api_get = fake_api_get
        candidates = select_pnap_sku.site_candidates(
            "https://example.invalid",
            "token",
            "ASH",
            0.30,
            64,
            6,
            2,
        )

        self.assertEqual([c["productCode"] for c in candidates], ["two.disk"])
        self.assertEqual(candidates[0]["storageDeviceCount"], 2)


if __name__ == "__main__":
    unittest.main()
