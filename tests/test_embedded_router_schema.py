from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]


def test_embedded_router_requires_live_port_and_sourceaddress_schema():
    peer = (ROOT / 'roles/openshift_evpn/tasks/peer.yml').read_text()
    canary = (ROOT / 'roles/openshift_evpn_embedded_router/tasks/canary.yml').read_text()
    schema = (ROOT / 'roles/openshift_evpn_embedded_router/tasks/schema.yml').read_text()
    assert "'port' in evpn_embedded_neighbor_properties" in schema
    assert "'sourceaddress' in evpn_embedded_neighbor_properties" in schema
    assert "'sourceaddress': evpn_site_public_ips[site_item.key]" in peer
    assert 'sourceaddress: "{{ evpn_embedded_public_ips[canary_site.key] }}"' in canary
    assert "'port': (evpn.embedded_router.listener_port | int)" in peer
    assert 'port: "{{ evpn.embedded_router.listener_port | int }}"' in canary


def test_embedded_router_uses_hostnetwork_public_endpoint_and_allows_hosting_vtep_nexthop():
    tasks = (ROOT / 'roles/openshift_evpn_embedded_router/tasks/main.yml').read_text()
    peer = (ROOT / 'roles/openshift_evpn/tasks/peer.yml').read_text()
    canary = (ROOT / 'roles/openshift_evpn_embedded_router/tasks/canary.yml').read_text()
    template = (ROOT / 'roles/openshift_evpn_embedded_router/templates/frr.conf.j2').read_text()
    openshift_main = (ROOT / 'roles/openshift_evpn/tasks/main.yml').read_text()
    retire = (ROOT / 'roles/retire_evpn_fabric_router/tasks/verify_site.yml').read_text()
    assert 'hostNetwork: true' in tasks
    assert 'dnsPolicy: ClusterFirstWithHostNet' in tasks
    assert 'hostPort:' not in tasks
    assert 'evpn_embedded_local_endpoint: "{{ evpn_embedded_public_endpoint }}"' in tasks
    assert 'evpn_canary_peer: "{{ evpn_embedded_public_endpoint }}"' in canary
    assert 'evpn_embedded_router_local_address: "{{ evpn_embedded_router_public_address }}"' in openshift_main
    assert 'evpn_embedded_router_local_address' in peer
    assert 'bgp listen range {{ evpn_embedded_public_ips.sw1 }}/32 peer-group EVPN-LEAVES' in template
    assert 'bgp listen range {{ evpn_embedded_public_ips.c1 }}/32 peer-group EVPN-LEAVES' in template
    assert 'bgp listen range 0.0.0.0/0' not in template
    assert 'neighbor EVPN-LEAVES attribute-unchanged next-hop' in template
    assert 'bgp allow-martian-nexthop' in template
    assert 'retire_site_peer: "{{ retire_evpn_public_ips[evpn.embedded_router.site] }}"' in retire


def test_authenticated_preflight_does_not_use_plain_tcp_probe_as_gate():
    tasks = (ROOT / 'roles/openshift_evpn_embedded_router/tasks/main.yml').read_text()
    assert 'plain TCP probes are intentionally skipped because TCP-MD5 rejects' in tasks
    assert 'when: not (evpn.bgp_auth.enabled | bool)' in tasks
    assert 'evpn_embedded_listener_probe.rc | int == 0' in tasks


def test_stale_direct_peering_mode_is_normalized_to_embedded_router():
    cfg = (ROOT / 'inventories/lab/group_vars/all.yml').read_text()
    assert "['fabric-router', 'direct-peering']" in cfg
    assert "'embedded-router'" in cfg


def test_live_crd_schema_path_uses_mapping_keys_not_dict_items_method():
    schema_tasks = (ROOT / 'roles/openshift_evpn_embedded_router/tasks/schema.yml').read_text()
    assert ".routers.items.properties" not in schema_tasks
    assert ".neighbors.items.properties" not in schema_tasks
    expected = "['routers']['items']['properties']['neighbors']['items']['properties']"
    assert expected in schema_tasks

    sample = {
        'schema': {
            'openAPIV3Schema': {
                'properties': {
                    'spec': {
                        'properties': {
                            'bgp': {
                                'properties': {
                                    'routers': {
                                        'items': {
                                            'properties': {
                                                'neighbors': {
                                                    'items': {
                                                        'properties': {
                                                            'address': {'type': 'string'},
                                                            'asn': {'type': 'integer'},
                                                            'port': {'type': 'integer'},
                                                            'sourceaddress': {'type': 'string'},
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    expression = Environment().compile_expression(
        "served['schema']['openAPIV3Schema']['properties']['spec']['properties']"
        "['bgp']['properties']['routers']['items']['properties']['neighbors']"
        "['items']['properties']"
    )
    props = expression(served=sample)
    assert props['port']['type'] == 'integer'
    assert props['sourceaddress']['type'] == 'string'


def test_embedded_router_requires_bidirectional_remote_vtep_after_cutover():
    verify = (ROOT / 'roles/openshift_evpn/tasks/verify.yml').read_text()
    assert 'Require bidirectional EVPN route propagation in embedded-router mode' in verify
    assert "show bgp l2vpn evpn route type 3" in verify
    assert "show evpn vni" in verify
    assert 'asymmetric' in verify and 'EVPN route propagation through the embedded route server' in verify
