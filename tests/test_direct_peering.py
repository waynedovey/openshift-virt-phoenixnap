from pathlib import Path
import re
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[1]


class DirectPeeringRepoTests(unittest.TestCase):
    def test_version_and_default_mode(self):
        self.assertEqual((ROOT / "VERSION").read_text().strip(), "1.4.31")
        text = (ROOT / "inventories/lab/group_vars/all.yml").read_text()
        self.assertIn("default('direct-peering', true)", text)
        self.assertIn("['fabric-router', 'embedded-router']", text)

    def test_runtime_neighbor_uses_standard_port_without_optional_schema_fields(self):
        peer = (ROOT / "roles/openshift_evpn/tasks/peer.yml").read_text()
        # The canonical neighbor must not emit the schema fields that failed on
        # the live OCP 4.22 CRD. Standard BGP port 179 is implicit.
        self.assertNotRegex(peer, r"['\"]port['\"]\s*:")
        self.assertNotRegex(peer, r"['\"]sourceaddress['\"]\s*:")
        self.assertIn("'address': evpn_peer_address", peer)
        self.assertIn("'asn': (evpn_peer_asn_effective | int)", peer)
        self.assertIn("'ebgpMultiHop': true", peer)

    def test_migration_preflights_tcp179_before_peer_reconciliation(self):
        main = (ROOT / "roles/openshift_evpn/tasks/main.yml").read_text()
        preflight = (ROOT / "roles/openshift_evpn/tasks/direct_preflight.yml").read_text()
        self.assertLess(
            main.index("direct_preflight.yml"),
            main.index("peer.yml"),
        )
        self.assertIn("/dev/tcp/{{ evpn_direct_remote_ip }}/179", preflight)
        self.assertIn("legacy external fabric router has not been retired", preflight)

    def test_no_embedded_route_server_runtime_remains(self):
        self.assertFalse((ROOT / "playbooks/07d_evpn_embedded_router.yml").exists())
        self.assertFalse((ROOT / "roles/openshift_evpn_embedded_router").exists())
        active_paths = [
            ROOT / "Makefile",
            ROOT / "site.yml",
            ROOT / "roles/openshift_evpn/tasks/main.yml",
            ROOT / "roles/openshift_evpn/tasks/peer.yml",
            ROOT / "playbooks/08_evpn.yml",
        ]
        for path in active_paths:
            text = path.read_text()
            self.assertNotIn("1179", text, path)
            self.assertNotIn("EVPN_EMBEDDED_ROUTER", text, path)

    def test_yaml_files_parse(self):
        # Ansible/Jinja expressions are quoted in these manifests, so basic YAML
        # parsing catches indentation/structure regressions without rendering.
        for path in ROOT.rglob("*.yml"):
            if any(part in {".venv", ".git"} for part in path.parts):
                continue
            with self.subTest(path=path.relative_to(ROOT)):
                with path.open() as fh:
                    list(yaml.safe_load_all(fh))


if __name__ == "__main__":
    unittest.main()
